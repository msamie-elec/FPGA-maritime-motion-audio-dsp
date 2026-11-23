from __future__ import annotations
import sys,os,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'host'))
import tkinter as tk
from maritime_gui import MaritimeGUI
from gui_pipeline import run_pipeline
r=tk.Tk();r.geometry('1500x870');app=MaritimeGUI(r);r.update()
app.make_demo();r.update()
print('demo loaded',app.source,'valid',app.source.exists() if app.source else False,flush=True)
t0=time.monotonic()
res=run_pipeline(app.source,app.trajectory,root/'build'/'gui_smoke_v08',None,profile='Normal')
print('pipeline',res.side_by_side,'elapsed',round(time.monotonic()-t0,2),flush=True)
app._accept_result(res)
assert app.result is not None
assert app.frames>0
r.update_idletasks();r.update()
print('implementation dims',app.left.winfo_width(),app.left.winfo_height(),flush=True)
if os.environ.get('SAVE_GUI_SCREENSHOT'):
 from PIL import ImageGrab
 ImageGrab.grab(bbox=(0,0,1500,870)).save('/mnt/data/Maritime_GUI_v08_video_preview.png')
app.main_tabs.select(app.assessment_tab);r.update_idletasks();r.update()
print('assessment chart dims',app.chartcanvas.get_tk_widget().winfo_width(),app.chartcanvas.get_tk_widget().winfo_height(),flush=True)
if os.environ.get('SAVE_GUI_SCREENSHOT'):
 from PIL import ImageGrab
 ImageGrab.grab(bbox=(0,0,1500,870)).save('/mnt/data/Maritime_GUI_v08_assessment_preview.png')
app._close();print('GUI_RESULT_SMOKE_PASS',flush=True)
