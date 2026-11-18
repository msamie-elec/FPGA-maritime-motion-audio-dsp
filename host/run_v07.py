"""Reproducible v0.7 three-axis video trial; physical port optional and explicit."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from gui_pipeline import run_pipeline


def main():
    p=argparse.ArgumentParser(description='Three-axis maritime camera stabilisation with SE(2) correction')
    p.add_argument('--video',required=True,type=Path,help='Compatible 30fps 18-496-frame clip')
    p.add_argument('--out',type=Path,default=Path('build/v07_trial'))
    p.add_argument('--port',default=None,help='Physical FPGA COM port; omit for SOFTWARE REFERENCE ONLY')
    p.add_argument('--profile',choices=['Normal','Strong'],default='Strong')
    z=p.parse_args()
    r=run_pipeline(z.video,None,z.out,z.port,z.profile)
    print(json.dumps({'video':str(r.side_by_side),'metric_status':r.metrics['image_stability']['status'],
       'image_jitter_reduction_pct':r.metrics['image_stability'].get('reduction_pct'),
       'filtered_axes':r.metrics.get('filtered_axes'),
       'hardware_verified':r.metrics['hardware_verified'],
       'profile':z.profile,'crop':r.metrics.get('crop')},indent=2))

if __name__=='__main__':main()
