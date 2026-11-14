"""Publication diagrams. Run from any directory; no data, API or credentials used."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(__file__).resolve().parents[1] / 'figures'
OUT.mkdir(parents=True, exist_ok=True)
NAVY, TEAL, ORANGE = '#17324D', '#137F80', '#C46A27'
GRAY, LIGHT, PALE = '#536475', '#EDF3F7', '#E8F5F2'
plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':8.5,
    'pdf.fonttype':42, 'ps.fonttype':42, 'savefig.facecolor':'white'})

def canvas(h):
    fig, ax = plt.subplots(figsize=(7.16,h))
    fig.subplots_adjust(left=.015,right=.985,bottom=.025,top=.98)
    ax.set(xlim=(0,100),ylim=(0,100)); ax.axis('off')
    return fig, ax

def txt(ax,x,y,s,size=8.5,color=NAVY,weight='normal',ha='left',va='center'):
    return ax.text(x,y,s,fontsize=size,color=color,weight=weight,ha=ha,va=va)

def box(ax,x,y,w,h,title,body='',color=NAVY,fill=LIGHT,ts=9,bs=8.3):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.45,rounding_size=1.5',
        lw=.9,edgecolor=color,facecolor=fill))
    if body:
        txt(ax,x+2,y+h-3,title,ts,color,'bold')
        txt(ax,x+2,y+h-8,body,bs,color,va='top')
    else:
        txt(ax,x+w/2,y+h/2,title,ts,color,'bold',ha='center')

def arrow(ax,x1,y1,x2,y2,color=GRAY,lw=1.1,style='-|>'):
    ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle=style,
                               mutation_scale=9,lw=lw,color=color))

def save(fig,name):
    fig.savefig(OUT/(name+'.pdf'))
    fig.savefig(OUT/(name+'.png'),dpi=200)
    plt.close(fig)

def motivation():
    fig,ax=canvas(2.35)
    txt(ax,1,97,'(a) Different evidence streams at the same revision moment',10,weight='bold')
    arrow(ax,24,88,98,88)
    txt(ax,98,92,'Schematic sequence (not measured time)',7.8,GRAY,ha='right')
    for x,label in [(26,'Earlier evidence'),(57,'Current analysis'),(81,'Speech onset')]:
        ax.plot([x,x],[41,86],color='#C5D0D9',lw=.7,ls=(0,(2,3)))
        txt(ax,x,84,label,7.5,GRAY,ha='center')
    txt(ax,1,73,'Chart evidence',8.5,weight='bold')
    box(ax,23,66,25,12,'Selected history: $S_A$',color=TEAL,fill=PALE,ts=8.4)
    box(ax,52,66,46,12,'Visible now: MG + dates + set $S_B$',ts=8.5)
    txt(ax,1,56,'Generated speech',8.5,weight='bold')
    box(ax,23,51,32,10,'Explanation about $S_A$',color=TEAL,fill=PALE,ts=8.3)
    box(ax,57,51,41,10,'Further explanation received',color=GRAY,fill=LIGHT,ts=8.2)
    txt(ax,1,42,'Browser playback',8.5,weight='bold')
    ax.plot([23,81],[42,42],color=TEAL,lw=5,solid_capstyle='butt')
    ax.plot([81,98],[42,42],color='#C8D4DC',lw=5,ls=(0,(2,2)))
    txt(ax,49,45.7,'Played portion refers to $S_A$',7.7,TEAL,ha='center')
    txt(ax,90,37,'Unplayed',7.5,GRAY,ha='center')
    ax.plot([81,81],[36,81],color=ORANGE,lw=1.2)
    box(ax,23,20,75,12,'“Use the group just discussed; edit charts 2/3; keep MG and dates.”',
        color=ORANGE,fill='#FFF5E9',ts=8.0)
    txt(ax,1,26,'User revision',8.5,weight='bold')
    arrow(ax,81,36,81,32,ORANGE)
    txt(ax,1,13,'(b) Correct binding',10,weight='bold')
    txt(ax,28,13,'Members $\leftarrow S_A$   |   Targets: 2 / 3   |   Scope: current MG + dates',8.5,TEAL,'bold')
    txt(ax,1,5,'Chart 1 remains unchanged. Reusing historical members does not restore the historical canvas.',8.3,GRAY)
    save(fig,'fig01_revision_timeline')

def architecture():
    fig,ax=canvas(2.50)
    txt(ax,1,97,'Shared full-duplex workspace',10,weight='bold')
    txt(ax,99,97,'Proposed study contract; no measured outcomes',7.6,GRAY,ha='right')
    box(ax,1,73,30,18,'Available evidence','History / exact saved sets\nCurrent charts / playback receipts',bs=7.6)
    box(ax,35,73,29,18,'User revision','Speech + selected references\nCurrent request / chart identities',bs=7.6)
    box(ax,68,73,31,18,'B0 / B2: shared contract','Same model, tools and evidence\nSame clarification / release policy',color=TEAL,fill=PALE,bs=7.6)
    arrow(ax,31,83,35,83)
    arrow(ax,49,73,49,71)
    ax.add_patch(FancyBboxPatch((1,42),98,29,boxstyle='round,pad=.45,rounding_size=1.5',
                              facecolor='white',edgecolor=TEAL,lw=1.1))
    txt(ax,3,67,'B2: inspectable revision card',9,TEAL,'bold')
    txt(ax,97,67,'B0: direct presentation, same execution',7.6,GRAY,ha='right')
    box(ax,3,43,29,20,'1  Evidence / origin','Historical source + version\nExact members (e.g., $S_A$)',color=TEAL,fill=PALE,bs=7.8)
    box(ax,35,43,29,20,'2  Targets / changes','Current chart IDs (e.g., 2/3)\nOnly requested field changes',color=TEAL,fill=PALE,bs=7.8)
    box(ax,67,43,30,20,'3  Retain / release','Keep: MG, dates, measures\nRelease: old member rule',color=TEAL,fill=PALE,bs=7.8)
    arrow(ax,49,42,49,37)
    box(ax,1,22,98,15,'Shared execution: direct and bound use the same compiler',
        'Resolve exact members  →  private candidate  →  real Olist SQL  →  request / version check  →  atomic commit',bs=7.9)
    txt(ax,1,14,'Separate evidence',8.4,weight='bold')
    for x,w,t,c in [(24,16,'Commit',NAVY),(43,16,'Render',NAVY),(62,16,'Visibility',NAVY),(81,18,'Playback',ORANGE)]:
        box(ax,x,9,w,9,t,color=c,fill=LIGHT if c==NAVY else '#FFF5E9',ts=8.2)
    txt(ax,1,3,'Event ledger links request, chart version and response; delivery does not establish human understanding.',7.9,GRAY)
    save(fig,'fig02_revision_architecture')

if __name__=='__main__':
    motivation()
    architecture()
    print(OUT)
