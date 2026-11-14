"""Faithful crops from an archived actual browser screenshot; no UI fabrication."""
from pathlib import Path
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SOURCE=Path(__file__).resolve().parent/'assets/workspace-source.png'
OUT=Path(__file__).resolve().parents[1]/'figures'
plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,'font.size':8})
im=Image.open(SOURCE)
assert im.size==(3840,2160)
fig=plt.figure(figsize=(7.16,3.45),facecolor='white')
navy='#17324D'

def label(x,y,s,size=8,weight='normal'):
    fig.text(x,y,s,fontsize=size,color=navy,weight=weight,va='center')

def crop(rect,where):
    ax=fig.add_axes(where)
    ax.imshow(im.crop(rect));ax.axis('off')

label(.01,.974,'Actual workspace: local scripted validation',9,'bold')
label(.01,.922,'(a) Same canvas, revision 8: chart 1 unchanged; service charts 2/3 remain Jan–Mar',8)
# Entire three-chart cards, without altering chart geometry, data or labels.
crop((208,1030,3035,2090),(.01,.284,.98,.625))
label(.01,.259,'(b) Historical evidence remains separate from the current canvas',8)
crop((208,751,3035,910),(.01,.165,.66,.085))
label(.695,.259,'(c) Latest reply outcome',8)
crop((3123,1342,3735,1447),(.695,.139,.295,.115))
label(.01,.108,'Crops from one real browser screenshot; no data or UI contents replaced.',7.7)
label(.01,.051,'Scripted speech/tool decisions + real Olist execution; no participant or real-model success claim.',7.7)
OUT.mkdir(parents=True,exist_ok=True)
fig.savefig(OUT/'fig03_actual_workspace.pdf',facecolor='white')
fig.savefig(OUT/'fig03_actual_workspace.png',dpi=200,facecolor='white')
plt.close(fig)
print(OUT/'fig03_actual_workspace.pdf')
