"""Build 16 multi-turn voice re-planning scenarios for CoVisStudio.

Outputs docs/voice_replan_scenarios.json (driver/oracle input, evaluator-private) and
docs/VOICE_REPLAN_SCENARIOS.md (human-readable). Run: python scripts/build_voice_scenarios.py Ground truth is cumulative: every user
turn's expected dashboard state is derived by applying that turn's patch to the
previous expected state, so later turns cannot silently contradict earlier ones.

Membership notation (resolved by the oracle at run time, never sent to the model):
  {"rule": "ranked", "top_n": 3, "rank_by": "orders"}
  {"rule": "fixed", "from": "H1:v1"}            members displayed by v1 in setup snapshot H1
  {"rule": "fixed", "from": "after:T5:v1"}      members displayed by v1 after turn 5 committed
  {"rule": "fixed", "from": "played:T2"}        categories named in the PLAYED part of turn 2
                                                (human-coded from played-sample cutoff)
"""
import json
from copy import deepcopy
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs"

YEAR = ("2017-01-01", "2018-01-01")
Q1 = ("2017-01-01", "2017-04-01")
H1_2017 = ("2017-01-01", "2017-07-01")
Q3 = ("2017-07-01", "2017-10-01")
Q4 = ("2017-10-01", "2018-01-01")
H2_2017 = ("2017-07-01", "2018-01-01")
Y2018 = ("2018-01-01", "2019-01-01")
H1_2018 = ("2018-01-01", "2018-07-01")
METRIC = {"v1": "orders", "v2": "low_review_rate", "v3": "avg_delivery_days"}
VIEWS = ("v1", "v2", "v3")
REGION_WORDS = {"RJ": "Rio de Janeiro", "MG": "Minas Gerais", "SP": "São Paulo"}


def ranked(n=3, by="orders"):
    return {"rule": "ranked", "top_n": n, "rank_by": by}


def fixed(origin):
    return {"rule": "fixed", "from": origin}


def view(vid, region, dates=YEAR, membership=None, **extra):
    return {"metric": METRIC[vid], "dimension": "category", "region": region,
            "start": dates[0], "end": dates[1], "status": "delivered",
            "membership": membership or ranked(), **extra}


def board(region, dates=YEAR, membership=None, per_view=None):
    state = {vid: view(vid, region, dates, membership) for vid in VIEWS}
    for vid, patch in (per_view or {}).items():
        state[vid].update(deepcopy(patch))
    return state


def dates(d):
    return {"start": d[0], "end": d[1]}


# Turn constructors -----------------------------------------------------------
def U(text, timing="after_end", offset_s=None, action="edit", patch=None, critical=(),
      tags=(), pauses=(), acceptable=(), note=""):
    return {"speaker": "user", "text": text,
            "timing": {"type": timing, **({"offset_s": offset_s} if offset_s is not None else {})},
            "pauses": [{"after_words": w, "ms": ms} for w, ms in pauses],
            "critical_words": list(critical), "tags": list(tags),
            "expect": {"action": action, "patch": patch or {},
                       "acceptable_alternatives": list(acceptable)},
            "note": note}


def A(kind, constraint=""):
    return {"speaker": "assistant", "expect": {"kind": kind}, "constraint": constraint}


# Scenarios -------------------------------------------------------------------
S = []

S.append(dict(
    id="S01", title="Seasonal reuse: first-quarter categories in the third quarter",
    goal="Compare service quality for the categories that led in Q1 against the current Q3 period in RJ.",
    replan=["REUSE", "RETAIN", "RETARGET", "REVERT"],
    setup={"history": {"H1": board("RJ", Q1)}, "current": board("RJ", Q3), "selection": None},
    turns=[
        U("What changed between the first quarter and now?", action="answer",
          tags=["NO-OP"], note="Discussion only; reading history must not restore it."),
        A("explain", "Compares H1 and current; must not edit."),
        U("Put the first-quarter categories into charts two and three, but keep the third quarter.",
          timing="barge_in", offset_s=3.0, critical=["first-quarter", "two", "three", "third quarter"],
          patch={"v2": {"membership": fixed("H1:v1")}, "v3": {"membership": fixed("H1:v1")}},
          tags=["BI", "NUM"], note="Historical members only; Q1 dates must NOT return."),
        A("confirm"),
        U("Chart one too.", critical=["one"], patch={"v1": {"membership": fixed("H1:v1")}},
          tags=["ELLIPSIS"], note="Elliptical retarget: same operation, add v1."),
        A("confirm"),
        U("Hmm, no, leave chart one showing this quarter's own top three.",
          timing="barge_in", offset_s=1.5, critical=["chart one", "own top three"],
          patch={"v1": {"membership": ranked(3)}}, tags=["BI", "REVERT"],
          note="Undo of the previous turn for v1 only, expressed as a rule, not Undo."),
        A("confirm"),
    ]))

S.append(dict(
    id="S02", title="Release a fixed set, then change and restore one ranking rule",
    goal="MG charts still carry RJ's fixed categories; the analyst wants MG's own leaders.",
    replan=["RELEASE", "SUPERSEDE", "REVERT"],
    setup={"history": {"H1": board("RJ")}, "current": board("MG", membership=fixed("H1:v1")), "selection": None},
    turns=[
        U("Which categories are these?", action="answer", tags=["NO-OP"]),
        A("answer", "Names the fixed RJ members; may say they are fixed."),
        U("Release the fixed categories and show Minas Gerais' own top three by orders, in all three charts.",
          timing="barge_in", offset_s=2.0, critical=["Release", "fixed", "top three", "orders", "all three"],
          patch={v: {"membership": ranked(3)} for v in VIEWS}, tags=["BI", "LEX", "NM"],
          note="Known ASR risk: 'Release' heard as 'These'."),
        A("confirm"),
        U("Rank chart three by delivery time instead.", critical=["chart three", "delivery time"],
          patch={"v3": {"membership": ranked(3, "avg_delivery_days")}}, tags=["NUM"],
          note="Ranking criterion only; v3 metric unchanged."),
        A("confirm"),
        U("No wait, keep chart three ranked by orders like the others.",
          timing="barge_in", offset_s=1.0, critical=["chart three", "orders"],
          patch={"v3": {"membership": ranked(3, "orders")}}, tags=["BI", "REVERT"]),
        A("confirm"),
    ]))

S.append(dict(
    id="S03", title="Replace a measure, abandon a half-spoken change, then rank one view",
    goal="Look at revenue for the frozen SP cohort without disturbing the service views.",
    replan=["REPLACE", "RETAIN", "CANCEL", "RELEASE"],
    setup={"history": {"H1": board("SP")}, "current": board("SP", membership=fixed("H1:v1")), "selection": None},
    turns=[
        U("Change chart one to revenue, keep everything else.", critical=["chart one", "revenue"],
          patch={"v1": {"metric": "revenue"}}, tags=["RETAIN"]),
        A("confirm"),
        U("Hmm, also chart three, show it for shipped orders. No, delivered is right, leave it.",
          timing="barge_in", offset_s=1.5, action="no_edit", critical=["shipped", "No", "leave it"],
          tags=["BI", "SC", "CANCEL"],
          note="Self-repair that ends in no change. Any status edit on v3 is an error."),
        A("answer", "Acknowledges chart three is unchanged."),
        U("Now rank chart one by revenue, top five.", critical=["rank", "revenue", "top five"],
          patch={"v1": {"membership": ranked(5, "revenue")}}, tags=["NUM"],
          note="Ranking releases v1's fixed set only; v2/v3 keep the fixed cohort."),
        A("confirm"),
    ]))

S.append(dict(
    id="S04", title="Backchannels during an explanation must not edit",
    goal="Listen to an explanation with natural acknowledgements, then narrow the view.",
    replan=["NO-OP", "NARROW"],
    setup={"history": {}, "current": board("SP", membership=ranked(5)), "selection": None},
    turns=[
        U("Explain why chart two looks high for one category.", action="answer", tags=["NO-OP"]),
        A("explain", "Long explanation (>8 s) so that backchannels land inside playback."),
        U("Mm-hm.", timing="backchannel", offset_s=3.0, action="no_edit", tags=["BC"],
          note="Current runtime revokes on every onset; record whether playback was cut and whether "
               "the explanation resumed. Any chart change is an error."),
        A("explain", "Continues or restarts the explanation."),
        U("Okay, right.", timing="backchannel", offset_s=2.0, action="no_edit", tags=["BC"]),
        A("explain"),
        U("Got it. Narrow all three to the top three.", critical=["all three", "top three"],
          patch={v: {"membership": ranked(3)} for v in VIEWS}, tags=["NUM"]),
        A("confirm"),
    ]))

S.append(dict(
    id="S05", title="Keep only the categories the assistant has already said",
    goal="Stop a spoken list part-way and freeze exactly the items heard so far.",
    replan=["FREEZE", "RETAIN"],
    setup={"history": {}, "current": board("RJ", membership=ranked(5)), "selection": None},
    turns=[
        U("Read me the five categories in chart one, from the largest.", action="answer",
          tags=["NO-OP"]),
        A("answer", "Lists five category names in rank order."),
        U("Stop, keep just the ones you've said so far, in all three charts.",
          timing="barge_in", offset_s=None, critical=["ones you've said", "all three"],
          patch={v: {"membership": fixed("played:T2")} for v in VIEWS}, tags=["BI", "DX"],
          acceptable=["clarify naming the played candidates"],
          note="THE full-duplex case. Inject after the 3rd category name has PLAYED "
               "(use playback receipts, not generated text). Truth = names in the played prefix; "
               "using all five, or names generated but not played, is an error."),
        A("confirm"),
        U("Switch to the second half of 2017.", critical=["second half", "2017"],
          patch={v: dates(H2_2017) for v in VIEWS}, tags=["NUM"],
          note="Frozen members kept; ranking must not return."),
        A("confirm"),
    ]))

S.append(dict(
    id="S06", title="Self-repair inside a date request, then a question that sounds like an edit",
    goal="Compare Q3 service metrics; decide later whether order volume follows.",
    replan=["NARROW", "NO-OP", "RETARGET"],
    setup={"history": {"H1": board("SP")}, "current": board("SP", membership=fixed("H1:v1")), "selection": None},
    turns=[
        U("Show the second quarter, sorry, third quarter of 2017 in charts two and three.",
          critical=["third quarter", "two", "three"], patch={"v2": dates(Q3), "v3": dates(Q3)},
          tags=["SC", "NUM"], note="Q2 dates anywhere is an error."),
        A("confirm"),
        U("And chart one stays the full year, right?", action="answer", tags=["NO-OP"],
          note="Yes/no question. Editing v1 is an error."),
        A("answer"),
        U("Actually put chart one on the same quarter.", timing="barge_in", offset_s=1.0,
          critical=["chart one", "same quarter"], patch={"v1": dates(Q3)}, tags=["BI", "ELLIPSIS"]),
        A("confirm"),
    ]))

S.append(dict(
    id="S07", title="An utterance split by a pause",
    goal="Bring SP's earlier leaders into MG service views, with natural hesitations.",
    replan=["REUSE", "RETAIN", "REPLACE"],
    setup={"history": {"H1": board("SP")}, "current": board("MG"), "selection": None},
    turns=[
        U("For charts two and three... use the categories from the São Paulo chart we looked at first.",
          pauses=[(5, 900)], critical=["two", "three", "São Paulo", "first"],
          patch={"v2": {"membership": fixed("H1:v1")}, "v3": {"membership": fixed("H1:v1")}},
          tags=["FR", "NM"], note="900 ms pause > 600 ms VAD silence. The first fragment alone must "
               "not produce a response or edit. MG must stay."),
        A("confirm"),
        U("Keep Minas Gerais... and the dates too.", pauses=[(3, 800)], action="no_edit",
          critical=["Keep", "Minas Gerais", "dates"], tags=["FR", "RETAIN"],
          note="Confirmation of retention; any edit is an error."),
        A("answer"),
        U("Change chart one to low-review rate.", critical=["chart one", "low-review rate"],
          patch={"v1": {"metric": "low_review_rate"}}, tags=["REPLACE"],
          note="v1 keeps top-3-by-orders membership; rank_by stays orders."),
        A("confirm"),
    ]))

S.append(dict(
    id="S08", title="Barge-in while the tool is still running",
    goal="Move service views to 2018 while order volume stays in 2017.",
    replan=["SUPERSEDE", "RETARGET", "RELEASE"],
    setup={"history": {"H1": board("RJ")},
           "current": board("RJ", per_view={"v2": {"membership": fixed("H1:v1")},
                                             "v3": {"membership": fixed("H1:v1")}}),
           "selection": None},
    turns=[
        U("Compare all three charts for 2018 instead.", critical=["all three", "2018"],
          patch={v: dates(Y2018) for v in VIEWS}, tags=["NUM"],
          note="Intermediate state; superseded by T2 for v1."),
        U("Only charts two and three, leave chart one in 2017.", timing="during_tool", offset_s=0.3,
          critical=["Only", "two and three", "chart one", "2017"], patch={"v1": dates(YEAR)},
          tags=["BT", "SUPERSEDE"],
          note="If T1 already committed, v1 must be explicitly restored to 2017 (a legal earlier "
               "commit stays legal). If T1 was revoked before commit, v2/v3 still need 2018."),
        A("confirm", "Must say which charts changed and that chart one is 2017."),
        U("Use their own top three by orders in 2018.", critical=["own top three", "orders"],
          patch={"v2": {"membership": ranked(3)}, "v3": {"membership": ranked(3)}}, tags=["RELEASE"],
          note="'their' = charts two and three."),
        A("confirm"),
    ]))

S.append(dict(
    id="S09", title="Wrong chart named, then corrected",
    goal="Revenue belongs on the order view; align delivery view to the same cohort.",
    replan=["RETARGET", "REVERT", "REUSE-CURRENT"],
    setup={"history": {"H1": board("SP")},
           "current": board("SP", membership=fixed("H1:v1"), per_view={"v3": {"membership": ranked(5)}}),
           "selection": None},
    turns=[
        U("Change chart two to revenue.", critical=["chart two", "revenue"],
          patch={"v2": {"metric": "revenue"}}, tags=[]),
        A("confirm"),
        U("Oh, I meant chart one, not two. Put chart two back to low-review rate.",
          timing="barge_in", offset_s=1.0, critical=["chart one", "not two", "low-review rate"],
          patch={"v1": {"metric": "revenue"}, "v2": {"metric": "low_review_rate"}},
          tags=["BI", "RETARGET"]),
        A("confirm"),
        U("And give chart three the same categories as chart one.",
          critical=["chart three", "same categories", "chart one"],
          patch={"v3": {"membership": fixed("after:T3:v1")}}, tags=["REUSE-CURRENT"],
          note="Source is the CURRENT chart one, not history; v3 top-5 ranking released."),
        A("confirm"),
        U("Good. Leave it there.", action="no_edit", tags=["NO-OP"]),
    ]))

S.append(dict(
    id="S10", title="Swap cohorts and come back to the first one",
    goal="Decide between RJ and SP leaders for an MG service review.",
    replan=["PROVENANCE-Q", "REUSE", "REVERT", "NARROW"],
    setup={"history": {"H1": board("RJ"), "H2": board("SP")},
           "current": board("MG", per_view={"v2": {"membership": fixed("H2:v1")},
                                             "v3": {"membership": fixed("H2:v1")}}),
           "selection": None},
    turns=[
        U("Which region did these categories come from?", action="answer", tags=["NO-OP"],
          note="Correct answer: São Paulo (H2). Tests provenance, not computation."),
        A("answer"),
        U("Swap them for the Rio ones.", timing="barge_in", offset_s=2.0, critical=["Swap", "Rio"],
          patch={"v2": {"membership": fixed("H1:v1")}, "v3": {"membership": fixed("H1:v1")}},
          tags=["BI", "NM"], note="MG stays."),
        A("confirm"),
        U("Hmm, the São Paulo set was better. Go back to that, but keep the current dates.",
          critical=["São Paulo", "Go back", "current dates"],
          patch={"v2": {"membership": fixed("H2:v1")}, "v3": {"membership": fixed("H2:v1")}},
          tags=["REVERT", "NM"], note="'Go back' is not Undo/restore of a whole version."),
        A("confirm"),
        U("And only the first half.", timing="barge_in", offset_s=1.0, critical=["first half"],
          patch={"v2": dates(H1_2017), "v3": dates(H1_2017)}, tags=["BI", "ELLIPSIS", "NUM"],
          note="Targets inherited from the previous turn (charts two and three)."),
        A("confirm"),
    ]))

S.append(dict(
    id="S11", title="Ambiguous 'those three' must trigger a question",
    goal="Choose between RJ historical leaders and MG current leaders.",
    replan=["CLARIFY", "REUSE"],
    setup={"history": {"H1": board("RJ")}, "current": board("MG"), "selection": None},
    turns=[
        U("Use those three categories in the service charts.", action="clarify",
          critical=["those three", "service charts"], tags=["CLARIFY"],
          note="Ambiguous: RJ historical top 3 vs MG current top 3. Expect one short question; "
               "any edit is a premature commit."),
        A("clarify", "Names both candidates."),
        U("The Rio ones.", critical=["Rio"],
          patch={"v2": {"membership": fixed("H1:v1")}, "v3": {"membership": fixed("H1:v1")}},
          tags=["NM", "ELLIPSIS"]),
        A("confirm"),
        U("Keep chart one as the local top three.", action="no_edit", tags=["RETAIN"]),
        A("answer"),
    ]))

S.append(dict(
    id="S12", title="Change order status without re-selecting categories",
    goal="Check canceled-order volume for the frozen SP cohort, then return to revenue.",
    replan=["SCOPE", "RETAIN", "REVERT", "REPLACE"],
    setup={"history": {"H1": board("SP")}, "current": board("SP", membership=fixed("H1:v1")), "selection": None},
    turns=[
        U("Show chart one for canceled orders instead of delivered.",
          critical=["chart one", "canceled", "delivered"], patch={"v1": {"status": "canceled"}},
          tags=["LEX"]),
        A("confirm"),
        U("Leave the categories as they are.", timing="barge_in", offset_s=1.0, action="no_edit",
          tags=["BI", "RETAIN"], note="Fixed set must not be re-ranked for canceled orders."),
        A("answer"),
        U("Charts two and three stay on delivered.", action="no_edit", tags=["RETAIN"]),
        A("answer"),
        U("Actually switch chart one back to delivered and make it revenue.",
          critical=["back to delivered", "revenue"],
          patch={"v1": {"status": "delivered", "metric": "revenue"}}, tags=["REVERT", "REPLACE"]),
        A("confirm"),
    ]))

S.append(dict(
    id="S13", title="Change grouping dimension and come back",
    goal="See where the SP cohort's orders come from, then analyse it in MG.",
    replan=["DIMENSION", "RETAIN", "SCOPE"],
    setup={"history": {"H1": board("SP")}, "current": board("SP", membership=fixed("H1:v1")), "selection": None},
    turns=[
        U("For chart one, break these categories down by customer state, all of Brazil.",
          critical=["customer state", "all of Brazil"],
          patch={"v1": {"dimension": "state", "region": None}}, tags=["NM"],
          note="Fixed categories become a filter; region cleared."),
        A("confirm"),
        U("Show it by month instead.", timing="barge_in", offset_s=1.5, critical=["month"],
          patch={"v1": {"dimension": "month"}}, tags=["BI", "SUPERSEDE"]),
        A("confirm"),
        U("Okay, back to categories, Minas Gerais.", critical=["categories", "Minas Gerais"],
          patch={"v1": {"dimension": "category", "region": "MG"}}, tags=["NM", "ELLIPSIS"],
          note="Fixed SP cohort retained under MG."),
        A("confirm"),
    ]))

S.append(dict(
    id="S14", title="Stacked elliptical edits, then freeze the current set",
    goal="Compare RJ order leaders with MG service quality for the same categories.",
    replan=["NARROW", "SCOPE", "RETARGET", "FREEZE"],
    setup={"history": {}, "current": board("RJ"), "selection": None},
    turns=[
        U("Make all three charts top five.", critical=["all three", "top five"],
          patch={v: {"membership": ranked(5)} for v in VIEWS}, tags=["NUM"]),
        A("confirm"),
        U("And Minas Gerais.", timing="barge_in", offset_s=1.0, critical=["Minas Gerais"],
          patch={v: {"region": "MG"} for v in VIEWS}, tags=["BI", "ELLIPSIS", "NM"]),
        A("confirm"),
        U("Wait, keep chart one in Rio.", timing="barge_in", offset_s=0.8, critical=["chart one", "Rio"],
          patch={"v1": {"region": "RJ"}}, tags=["BI", "SUPERSEDE"]),
        A("confirm"),
        U("And freeze the Rio categories from chart one into charts two and three.",
          critical=["freeze", "chart one", "two and three"],
          patch={"v2": {"membership": fixed("after:T5:v1")}, "v3": {"membership": fixed("after:T5:v1")}},
          tags=["FREEZE"], note="Members = RJ top 5 shown by v1 after T5; v2/v3 stay MG."),
        A("confirm"),
    ]))

S.append(dict(
    id="S15", title="Hypotheticals, polite requests and 'fix it'",
    goal="Move order volume to revenue and service views to Q4.",
    replan=["NO-OP", "CONFIRM", "NARROW", "ALIGN"],
    setup={"history": {}, "current": board("SP", membership=ranked(5)), "selection": None},
    turns=[
        U("What if we used revenue in chart one?", action="answer", tags=["NO-OP", "LEX"],
          acceptable=["clarify"], note="Hypothetical. Editing now is a premature commit."),
        A("answer"),
        U("Yes, do it.", critical=["do it"], patch={"v1": {"metric": "revenue"}}, tags=["ELLIPSIS"]),
        A("confirm"),
        U("Could chart three show the last quarter of 2017?", critical=["chart three", "last quarter"],
          patch={"v3": dates(Q4)}, tags=["NUM"], note="Polite request = edit."),
        A("confirm"),
        U("Fix it so chart two matches.", timing="barge_in", offset_s=1.0,
          critical=["chart two", "matches"], patch={"v2": dates(Q4)}, tags=["BI", "LEX"],
          note="Match = dates only; v2 metric unchanged."),
        A("confirm"),
    ]))

S.append(dict(
    id="S16", title="Cumulative flow (replicates the failed 2026-11-13 run)",
    goal="Reuse RJ leaders in MG service views, narrow time, then release one view.",
    replan=["REUSE", "NARROW", "SUPERSEDE", "RELEASE"],
    setup={"history": {"H1": board("RJ")}, "current": board("MG"), "selection": None},
    turns=[
        U("Give me a quick read of the three charts.", action="answer", tags=["NO-OP"]),
        A("explain"),
        U("Bring the Rio categories into charts two and three, keep Minas Gerais.",
          timing="barge_in", offset_s=3.0, critical=["Rio", "two and three", "Minas Gerais"],
          patch={"v2": {"membership": fixed("H1:v1")}, "v3": {"membership": fixed("H1:v1")}},
          tags=["BI", "NM"]),
        A("confirm"),
        U("Just the first half.", critical=["first half"],
          patch={"v2": dates(H1_2017), "v3": dates(H1_2017)}, tags=["ELLIPSIS", "NUM"]),
        A("confirm"),
        U("No, first quarter.", timing="barge_in", offset_s=1.0, critical=["first quarter"],
          patch={"v2": dates(Q1), "v3": dates(Q1)}, tags=["BI", "SUPERSEDE"]),
        A("confirm"),
        U("Now drop the Rio set in chart two and show its own top three by orders.",
          critical=["drop", "chart two", "top three", "orders"],
          patch={"v2": {"membership": ranked(3)}}, tags=["RELEASE"],
          note="v3 keeps RJ members and Q1."),
    ]))

# Calibrated against archived real runs: <=25-word replies took ~8 s; explanations 10-15 s.
# Later re-planning turns: every scenario has 5-9 user turns ------------------
EXTRA = {
    "S01": [
        U("Show chart one as revenue.", critical=["chart one", "revenue"],
          patch={"v1": {"metric": "revenue"}}, tags=["REPLACE"],
          note="Measure only; v1 stays this quarter's top three by orders."),
        A("confirm"),
        U("And rank it by revenue too.", timing="barge_in", offset_s=1.0, critical=["rank", "revenue"],
          patch={"v1": {"membership": ranked(3, "revenue")}}, tags=["BI", "ELLIPSIS"]),
        A("confirm"),
    ],
    "S02": [
        U("Make it the top five in chart one only.", critical=["top five", "chart one only"],
          patch={"v1": {"membership": ranked(5)}}, tags=["NUM", "RETARGET"]),
        A("confirm"),
        U("Actually, top four.", timing="barge_in", offset_s=1.0, critical=["top four"],
          patch={"v1": {"membership": ranked(4)}}, tags=["BI", "SUPERSEDE", "NUM"]),
        A("confirm"),
    ],
    "S03": [
        U("Put charts two and three on the second half of 2017.", critical=["two and three", "second half"],
          patch={"v2": dates(H2_2017), "v3": dates(H2_2017)}, tags=["NUM"]),
        A("confirm"),
        U("Keep the same categories there.", timing="barge_in", offset_s=1.0, action="no_edit",
          tags=["BI", "RETAIN"], note="Retention confirmation; re-ranking v2/v3 is an error."),
        A("answer"),
        U("And chart one too, same half.", critical=["chart one", "same half"],
          patch={"v1": dates(H2_2017)}, tags=["ELLIPSIS"]),
        A("confirm"),
    ],
    "S04": [
        U("Switch to Minas Gerais.", critical=["Minas Gerais"],
          patch={v: {"region": "MG"} for v in VIEWS}, tags=["NM"]),
        A("confirm"),
        U("Okay.", timing="backchannel", offset_s=1.0, action="no_edit", tags=["BC"]),
        A("confirm"),
        U("Mm-hm, and chart two by revenue.", critical=["chart two", "revenue"],
          patch={"v2": {"metric": "revenue"}}, tags=["LEX"],
          note="Starts with an acknowledgement but is a request; must not be held as a backchannel."),
        A("confirm"),
    ],
    "S05": [
        U("Read me the delivery times for those.", action="answer", tags=["NO-OP"]),
        A("answer"),
        U("Change chart one to revenue.", timing="barge_in", offset_s=2.0, critical=["chart one", "revenue"],
          patch={"v1": {"metric": "revenue"}}, tags=["BI", "REPLACE"]),
        A("confirm"),
        U("Leave the categories frozen.", action="no_edit", tags=["RETAIN"]),
        A("answer"),
    ],
    "S06": [
        U("Now the fourth quarter for all three.", critical=["fourth quarter", "all three"],
          patch={v: dates(Q4) for v in VIEWS}, tags=["NUM"]),
        A("confirm"),
        U("No, sorry, just charts two and three; chart one stays in the third quarter.",
          timing="barge_in", offset_s=1.0, critical=["just charts two and three", "third quarter"],
          patch={"v1": dates(Q3)}, tags=["BI", "SC", "RETARGET"]),
        A("confirm"),
        U("Is chart three still the delivery time?", action="answer", tags=["NO-OP"]),
        A("answer"),
    ],
    "S07": [
        U("Chart one... back to orders.", pauses=[(2, 900)], critical=["chart one", "orders"],
          patch={"v1": {"metric": "orders"}}, tags=["FR", "REVERT"]),
        A("confirm"),
        U("And for all three, only canceled... no, keep delivered orders.", action="no_edit",
          critical=["no", "delivered"], tags=["SC", "CANCEL"], note="Any status change is an error."),
        A("answer"),
        U("Use the first quarter of 2017 for charts two and three.", critical=["first quarter", "two and three"],
          patch={"v2": dates(Q1), "v3": dates(Q1)}, tags=["NUM"]),
        A("confirm"),
    ],
    "S08": [
        U("Make charts one and two revenue.", critical=["one and two", "revenue"],
          patch={"v1": {"metric": "revenue"}, "v2": {"metric": "revenue"}}, tags=["REPLACE"],
          note="Intermediate; superseded by the next turn for chart two."),
        U("Only chart one.", timing="during_tool", offset_s=0.3, critical=["Only", "chart one"],
          patch={"v2": {"metric": "low_review_rate"}}, tags=["BT", "SUPERSEDE"]),
        A("confirm"),
        U("And show chart one for 2018 as well.", critical=["chart one", "2018"],
          patch={"v1": dates(Y2018)}, tags=["NUM"]),
        A("confirm"),
    ],
    "S09": [
        U("Actually, rank chart three by its own top five orders again.",
          critical=["chart three", "top five", "orders"], patch={"v3": {"membership": ranked(5)}},
          tags=["RELEASE", "REVERT"]),
        A("confirm"),
        U("Top three, not five.", timing="barge_in", offset_s=1.0, critical=["top three"],
          patch={"v3": {"membership": ranked(3)}}, tags=["BI", "SC", "NUM"]),
        A("confirm"),
    ],
    "S10": [
        U("Show the same for chart one, but keep it ranked.", critical=["chart one", "ranked"],
          patch={"v1": dates(H1_2017)}, tags=["ELLIPSIS", "RETAIN"],
          note="'the same' = first half; v1 keeps its MG top-3 ranking."),
        A("confirm"),
        U("Which set are charts two and three using now?", action="answer", tags=["NO-OP"],
          note="Correct answer: the São Paulo set (H2)."),
        A("answer"),
    ],
    "S11": [
        U("Show charts two and three for São Paulo, same categories.",
          critical=["two and three", "São Paulo", "same categories"],
          patch={"v2": {"region": "SP"}, "v3": {"region": "SP"}}, tags=["NM", "RETAIN"]),
        A("confirm"),
        U("And chart one too, São Paulo's own top three.", timing="barge_in", offset_s=1.0,
          critical=["chart one", "São Paulo", "top three"], patch={"v1": {"region": "SP"}},
          tags=["BI", "NM"]),
        A("confirm"),
        U("Use the same three in all charts... I mean the Rio ones.", critical=["Rio"],
          patch={"v1": {"membership": fixed("H1:v1")}}, tags=["SC"],
          note="Self-repair resolves 'the same three' to the RJ set; v1 stays in SP."),
        A("confirm"),
    ],
    "S12": [
        U("Show charts two and three for 2018.", critical=["two and three", "2018"],
          patch={"v2": dates(Y2018), "v3": dates(Y2018)}, tags=["NUM"]),
        A("confirm"),
        U("Hmm, only the first half of 2018.", timing="barge_in", offset_s=1.0, critical=["first half", "2018"],
          patch={"v2": dates(H1_2018), "v3": dates(H1_2018)}, tags=["BI", "SUPERSEDE", "NUM"]),
        A("confirm"),
    ],
    "S13": [
        U("Show chart two by month for these categories, all of Brazil.",
          critical=["chart two", "month", "all of Brazil"],
          patch={"v2": {"dimension": "month", "region": None}}, tags=["DIMENSION"]),
        A("confirm"),
        U("Actually, chart two only for São Paulo.", timing="barge_in", offset_s=1.0,
          critical=["chart two", "São Paulo"], patch={"v2": {"region": "SP"}}, tags=["BI", "NM"]),
        A("confirm"),
        U("Back to categories for chart two.", critical=["categories", "chart two"],
          patch={"v2": {"dimension": "category"}}, tags=["REVERT"]),
        A("confirm"),
    ],
    "S14": [
        U("Now the first half of 2017 for everything.", critical=["first half", "everything"],
          patch={v: dates(H1_2017) for v in VIEWS}, tags=["NUM"],
          note="v1 is still a dynamic ranking, so its members may change; v2/v3 stay frozen."),
        A("confirm"),
        U("But don't let chart one re-rank; keep the categories it had.", timing="barge_in", offset_s=1.0,
          critical=["chart one", "re-rank", "categories it had"],
          patch={"v1": {"membership": fixed("after:T7:v1")}}, tags=["BI", "FREEZE"],
          note="Members = v1's full-year RJ top five before the date change; H1 dates kept."),
        A("confirm"),
    ],
    "S15": [
        U("What would chart one look like for Rio?", action="answer", tags=["NO-OP"],
          acceptable=["clarify"], note="Hypothetical; editing now is a premature commit."),
        A("answer"),
        U("Go ahead.", critical=["Go ahead"], patch={"v1": {"region": "RJ"}}, tags=["ELLIPSIS"]),
        A("confirm"),
        U("And the other two as well.", timing="barge_in", offset_s=1.0, critical=["other two"],
          patch={"v2": {"region": "RJ"}, "v3": {"region": "RJ"}}, tags=["BI", "ELLIPSIS"]),
        A("confirm"),
    ],
    "S16": [
        A("confirm"),
        U("Change chart three to revenue.", critical=["chart three", "revenue"],
          patch={"v3": {"metric": "revenue"}}, tags=["REPLACE"]),
        A("confirm"),
        U("Keep the Rio set there.", timing="barge_in", offset_s=1.0, action="no_edit",
          critical=["Rio"], tags=["BI", "RETAIN"]),
        A("answer"),
        U("And put chart one on the first quarter too.", critical=["chart one", "first quarter"],
          patch={"v1": dates(Q1)}, tags=["ELLIPSIS"]),
        A("confirm"),
        U("Done, thanks.", action="no_edit", tags=["NO-OP"], note="Closing; any edit is an error."),
        A("answer"),
    ],
}
for _scenario in S:
    _scenario["turns"].extend(EXTRA[_scenario["id"]])

ASSISTANT_SECONDS = {"explain": 12.0, "answer": 7.0, "confirm": 7.0, "clarify": 5.0}


def build():
    out = []
    for sc in S:
        state = deepcopy(sc["setup"]["current"])
        turns, est = [], 0.0
        for n, turn in enumerate(sc["turns"], start=1):
            turn = {"turn": n, **deepcopy(turn)}
            if turn["speaker"] == "user":
                words = len(turn["text"].split())
                est += words / 2.5 + sum(p["ms"] for p in turn["pauses"]) / 1000 + 0.6 + (1.5 if turn["expect"]["action"] == "edit" else 0)
                patch = turn["expect"]["patch"]
                assert (turn["expect"]["action"] == "edit") == bool(patch), (sc["id"], n)
                before = deepcopy(state)
                for vid, fields in patch.items():
                    assert vid in state and set(fields) <= set(state[vid]), (sc["id"], n, fields)
                    state[vid].update(deepcopy(fields))
                turn["expect"]["changed_views"] = sorted(v for v in VIEWS if state[v] != before[v])
                assert turn["expect"]["action"] != "edit" or turn["expect"]["changed_views"], (sc["id"], n)
                turn["expect"]["state_after"] = deepcopy(state)
            else:
                nxt = sc["turns"][n] if n < len(sc["turns"]) else None
                full = ASSISTANT_SECONDS[turn["expect"]["kind"]]
                if nxt and nxt["speaker"] == "user" and nxt["timing"]["type"] in ("barge_in", "backchannel"):
                    full = nxt["timing"].get("offset_s") or 4.0
                est += full + 2.0  # response latency
            turns.append(turn)
        users = [t for t in turns if t["speaker"] == "user"]
        assert 5 <= len(users) <= 9, (sc["id"], len(users))
        out.append({**{k: v for k, v in sc.items() if k != "turns"}, "turns": turns,
                    "final_state": state,
                    "summary": {"turns": len(turns), "user_turns": len(users),
                                "edit_turns": sum(t["expect"]["action"] == "edit" for t in users),
                                "no_edit_turns": sum(t["expect"]["action"] in ("no_edit", "answer") for t in users),
                                "clarify_turns": sum(t["expect"]["action"] == "clarify" for t in users),
                                "estimated_voice_seconds": round(est, 1)}})
    return out


def fmt_members(m):
    if m["rule"] == "ranked":
        return f"top {m['top_n']} by {m['rank_by']}"
    src = m["from"]
    if src.startswith("played:"):
        return f"fixed = names PLAYED in {src.split(':')[1]}"
    if src.startswith("after:"):
        _, t, v = src.split(":")
        return f"fixed = {v} members after {t}"
    h, v = src.split(":")
    return f"fixed = {v} members in {h}"


def fmt_view(s):
    region = s["region"] or "all regions"
    status = "" if s["status"] == "delivered" else f", {s['status']}"
    dim = "" if s["dimension"] == "category" else f", by {s['dimension']}"
    return f"{s['metric']}{dim} · {region} · {s['start']}→{s['end']}{status} · {fmt_members(s['membership'])}"


def fmt_patch(patch):
    parts = []
    for vid, fields in patch.items():
        bits = []
        for key, value in fields.items():
            if key == "membership":
                bits.append(fmt_members(value))
            elif key == "start":
                bits.append(f"{value}→{fields['end']}")
            elif key == "end":
                continue
            else:
                bits.append(f"{key}={value}")
        parts.append(f"{vid}: " + ", ".join(bits))
    return "; ".join(parts)


def fmt_timing(t):
    kind = t["type"]
    if kind == "after_end":
        return "after reply"
    off = t.get("offset_s")
    label = {"barge_in": "barge-in", "backchannel": "backchannel", "during_tool": "during tool"}[kind]
    if off is None:
        return f"{label} (see note)"
    return f"{label} +{off:g}s"


def markdown(data):
    lines = []
    total_turns = sum(s["summary"]["turns"] for s in data)
    total_user = sum(s["summary"]["user_turns"] for s in data)
    tag_counts = {}
    for s in data:
        for t in s["turns"]:
            for tag in t.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    lines += [
        "# Voice re-planning scenarios (16 scenarios × 5–9 user voice turns)",
        "",
        "Evaluator-private. Never place this file, its ground truth or its notes in model context.",
        f"Generated by `scripts/build_voice_scenarios.py`; {len(data)} scenarios, {total_turns} turns, "
        f"{total_user} user utterances.",
        "",
        "## Setup common to all scenarios",
        "",
        "Three charts grouped by product category, delivered orders, calendar 2017 unless the setup says otherwise:",
        "v1 = orders, v2 = low-review rate, v3 = average delivery days. `H1`, `H2` are committed "
        "historical snapshots built before voice starts; `current` is the canvas when voice starts.",
        "Category members are never written here: the oracle resolves `fixed = v1 members in H1` "
        "from the actual snapshot, so scenarios stay valid if the data changes.",
        "",
        "## Turn timing",
        "",
        "| Code | Injection point |",
        "| --- | --- |",
        "| after reply | after the previous assistant playback ends (natural turn-taking) |",
        "| barge-in +Ns | N seconds after the first **played** sample of the assistant reply (playback receipts, not generated text) |",
        "| backchannel +Ns | as barge-in; a short acknowledgement that should not change charts |",
        "| during tool +Ns | N seconds after the previous user speech end, before that request's receipt |",
        "",
        "## Tags",
        "",
        "Voice phenomena: BI barge-in · BT barge-in during tool · BC backchannel · SC self-correction · "
        "FR pause-fragmented utterance · DX reference to played speech · NM spoken place name · "
        "NUM spoken number/date · LEX confusable word · ELLIPSIS elliptical follow-up. "
        "Other tags (NO-OP, RETAIN, REVERT, SUPERSEDE, RELEASE …) label the intent move.",
        "",
        "Tag counts: " + ", ".join(f"{k} {v}" for k, v in sorted(tag_counts.items())),
        "",
        "## Per-turn scoring and error attribution",
        "",
        "For every user turn record: (1) action correct (edit / no edit / clarify / answer); "
        "(2) each view's committed source equals `state_after` (oracle + independent SQL); "
        "(3) untouched views unchanged; (4) spoken claim consistent with the request's receipt; "
        "(5) ASR: every critical word recovered in the transcript.",
        "",
        "Attribute each failure to exactly one first cause, in this order:",
        "",
        "1. **ASR** — a critical word is wrong or missing in the transcript.",
        "2. **Segmentation/timing** — VAD fragment answered early, stale tool, request revoked before its work ran.",
        "3. **Decision** — transcript is right but the targets, scope or membership rule are wrong.",
        "4. **Contract/execution** — tool rejected or protocol error.",
        "5. **Claim** — the reply says a change happened that the receipt does not show.",
        "",
        "Run each scenario twice: **voice** (TTS clips injected at the timings above) and a **text twin** "
        "(same utterances typed, no timing). The difference isolates what voice adds; the text twin "
        "also shows the decision error rate without ASR.",
        "",
        "## Overview",
        "",
        "| ID | Title | Messages | User turns | Edits | No-edit | Clarify | Est. voice s | Re-plan types |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for s in data:
        m = s["summary"]
        lines.append(f"| {s['id']} | {s['title']} | {m['turns']} | {m['user_turns']} | {m['edit_turns']} | "
                     f"{m['no_edit_turns']} | {m['clarify_turns']} | {m['estimated_voice_seconds']} | "
                     f"{', '.join(s['replan'])} |")
    estimates = [s["summary"]["estimated_voice_seconds"] for s in data]
    over = [s["id"] for s in data if s["summary"]["estimated_voice_seconds"] > 60]
    lines += ["", f"Estimated voice time is {min(estimates)}–{max(estimates)} s per scenario (user speech at "
              "2.5 words/s; assistant confirmations ~7 s and explanations ~12 s, calibrated against archived "
              "runs; replies cut at barge-in points; 2 s response latency; 1.5 s per committed tool). "
              + (f"{len(over)} of {len(estimates)} scenarios exceed" if over else "Several scenarios approach")
              + " the 60 s formal-study voice window, and earlier runs lost otherwise correct trials to that "
              "budget. Diagnostic runs therefore use a separate, recorded budget "
              "(`run_voice_scenarios.py --budget-seconds`, default 150 s, sets `COVIS_VOICE_BUDGET_SECONDS`; "
              f"the longest estimate plus a 30 s margin is {int(max(estimates)) + 30} s). Formal-study tasks keep 60 s.", ""]
    for s in data:
        lines += [f"## {s['id']} — {s['title']}", "", f"**Goal.** {s['goal']}", ""]
        setup = s["setup"]
        lines += ["**Setup.**", ""]
        for label, snap in setup["history"].items():
            lines.append(f"- {label}: " + "; ".join(f"{v} {fmt_view(snap[v])}" for v in VIEWS))
        lines.append("- current: " + "; ".join(f"{v} {fmt_view(setup['current'][v])}" for v in VIEWS))
        lines += ["", "| # | Who | Timing | Utterance / expected behaviour | Expected change | Tags |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for t in s["turns"]:
            if t["speaker"] == "user":
                text = t["text"]
                for p in t["pauses"]:
                    words = text.split()
                    text = " ".join(words[:p["after_words"]]) + f" [pause {p['ms']} ms] " + " ".join(words[p["after_words"]:])
                exp = t["expect"]
                change = fmt_patch(exp["patch"]) if exp["patch"] else f"**{exp['action'].replace('_', ' ')}**"
                if exp["acceptable_alternatives"]:
                    change += f" (also OK: {'; '.join(exp['acceptable_alternatives'])})"
                note = f"<br>_{t['note']}_" if t["note"] else ""
                lines.append(f"| T{t['turn']} | User | {fmt_timing(t['timing'])} | “{text}”{note} | {change} | "
                             f"{' '.join(t['tags'])} |")
            else:
                c = f": {t['constraint']}" if t["constraint"] else ""
                lines.append(f"| T{t['turn']} | Assistant | — | _{t['expect']['kind']}{c}_ | — | |")
        lines += ["", "**Expected views after each user turn** (bold = changed by that turn).", "",
                  "| After | v1 | v2 | v3 |", "| --- | --- | --- | --- |"]
        lines.append("| setup | " + " | ".join(fmt_view(setup["current"][v]) for v in VIEWS) + " |")
        for t in s["turns"]:
            if t["speaker"] != "user":
                continue
            cells = []
            for v in VIEWS:
                cell = fmt_view(t["expect"]["state_after"][v])
                cells.append(f"**{cell}**" if v in t["expect"]["changed_views"] else cell)
            lines.append(f"| T{t['turn']} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    data = build()
    payload = {"protocol": "covis-voice-replan-0.1",
               "visibility": "evaluator-private; never inject into model context",
               "membership_notation": __doc__.split("Membership notation")[1].strip(),
               "scenarios": data}
    (OUT / "voice_replan_scenarios.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "VOICE_REPLAN_SCENARIOS.md").write_text(markdown(data), encoding="utf-8")
    for s in data:
        print(s["id"], s["summary"])
