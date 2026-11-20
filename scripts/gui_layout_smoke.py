from __future__ import annotations
import os, sys, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
import tkinter as tk
from maritime_gui import MaritimeGUI

r=tk.Tk();app=MaritimeGUI(r)
r.update_idletasks();r.update()
print('tab_labels',[app.main_tabs.tab(i,'text') for i in range(app.main_tabs.index('end'))])
print('initial_geometry',r.winfo_width(),r.winfo_height())
print('implementation_video',app.left.winfo_width(),app.left.winfo_height(),app.right.winfo_width(),app.right.winfo_height())
assert [app.main_tabs.tab(i,'text') for i in range(app.main_tabs.index('end'))]==['Implementation','Video Assessment','Audio Assessment','Help']
assert app.left.winfo_width()>400 and app.left.winfo_height()>300
for resolution in [(1366,768),(1726,896)]:
 r.geometry(f'{resolution[0]}x{resolution[1]}');r.update_idletasks();r.update()
 print('resize',resolution,'video',app.left.winfo_width(),app.left.winfo_height())
 assert app.left.winfo_width()>400 and app.left.winfo_height()>250
 r.after(250,lambda:None);r.update()
 if os.environ.get('SAVE_GUI_SCREENSHOT'):
  try:
   from PIL import ImageGrab
   ImageGrab.grab(bbox=(0,0,resolution[0],resolution[1])).save('/mnt/data/Maritime_GUI_v08_'+str(resolution[0])+'.png')
  except Exception as e: print('screenshot',e)
app.main_tabs.select(app.assessment_tab);r.update_idletasks();r.update()
print('assessment_chart_dims',app.chartcanvas.get_tk_widget().winfo_width(),app.chartcanvas.get_tk_widget().winfo_height())
assert app.chartcanvas.get_tk_widget().winfo_height()>300
for value in ('Frequency spectrum','Image stability','Evidence log','Motion curves'):
 app.assess_view.set(value);app._show_assessment_view();r.update_idletasks();r.update();print('assess view',value)
app.main_tabs.select(app.audio_assessment_tab);r.update_idletasks();r.update()
print('audio_chart_dims',app.audiocanvas.get_tk_widget().winfo_width(),app.audiocanvas.get_tk_widget().winfo_height())
assert app.audiocanvas.get_tk_widget().winfo_height()>300
app.show_help('Program Arty A7');r.update_idletasks();r.update()
assert app.main_tabs.select()==str(app.help_tab)
print('help_chars',len(app.help_text.get('1.0','end')))
if os.environ.get('SAVE_GUI_SCREENSHOT'):
 try:
  from PIL import ImageGrab
  ImageGrab.grab(bbox=(0,0,r.winfo_width(),r.winfo_height())).save('/mnt/data/Maritime_GUI_v08_help.png')
 except Exception as e:print('screenshot',e)
app._close()
print('GUI_LAYOUT_SMOKE_PASS')
