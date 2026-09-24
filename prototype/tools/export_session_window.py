"""List/export actual indexed model windows without inference. See README_SESSIONS.md."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.paths import ApplicationLock,default_data_root
from app.sessions import SessionStore,records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',type=Path,default=default_data_root())
    parser.add_argument('--conversation',required=True)
    parser.add_argument('--epoch',required=True)
    parser.add_argument('--window',help='Omit to list window IDs and source intervals')
    parser.add_argument('--output',type=Path,help='New .npy path outside the conversation')
    parser.add_argument('--consent-export',action='store_true',help='Acknowledge sensitive unencrypted local audio export')
    args=parser.parse_args()
    if args.window and (not args.output or not args.consent_export):parser.error('Export requires --output and --consent-export')
    owner=ApplicationLock(args.data_root)
    try:
        store=SessionStore(args.data_root)
        if args.window:
            print(store.export_window(args.conversation,args.epoch,args.window,args.output))
        else:
            for row in records(store.epoch(args.conversation,args.epoch)/'windows.jsonl'):
                print(json.dumps(row))
    finally:owner.close()


if __name__=='__main__':main()
