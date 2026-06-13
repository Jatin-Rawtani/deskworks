"""Deskworks command-line interface.

  deskworks init                 # write a starter deskworks.toml here
  deskworks ingest               # pre-extract + cache PDF full text
  deskworks index                # build the hybrid search index
  deskworks ask "question"       # one-shot answer in the terminal
  deskworks ask                  # interactive Q&A loop
  deskworks web                  # start the browser chat (foreground)
  deskworks summarize <folder> <name>   # bulk local summaries -> md/csv
  deskworks dashboard <csv>      # build a searchable HTML dashboard
  deskworks status               # show config + index + model reachability
"""
from __future__ import annotations
import os, sys, json, shutil, urllib.request

from . import __version__
from .config import load as load_config


def _cfg(args):
    return load_config(args.config)


def cmd_init(args):
    dest = "deskworks.toml"
    if os.path.exists(dest):
        print(f"{dest} already exists — not overwriting.")
        return
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    example = os.path.join(here, "deskworks.toml.example")
    if os.path.exists(example):
        shutil.copy(example, dest)
    else:  # installed as a package without the example shipped
        from .config import DEFAULTS
        import tomllib  # noqa
        print("# edit this file", file=sys.stderr)
    print(f"Wrote {dest}. Edit [corpus].paths and [llm] to match your setup, then run:\n"
          f"  deskworks ingest && deskworks index && deskworks web")


def cmd_ingest(args):
    from .ingest import parse_all_pdfs
    parse_all_pdfs(_cfg(args))


def cmd_index(args):
    cfg = _cfg(args)
    # use Apple GPU (MPS) for the one-time build if available; serving uses CPU
    try:
        import torch
        if torch.backends.mps.is_available() and cfg.embed["device"] == "cpu":
            os.environ.setdefault("DESKWORKS_EMBED_DEVICE", "mps")
    except Exception:
        pass
    from . import core
    import time
    t = time.time()
    n = core.build_index(cfg, verbose=True)
    print(f"\nDone — {n} chunks in {time.time()-t:.0f}s.")


def _show(cfg, q):
    from . import core
    res = core.answer(cfg, q)
    print("\n" + res["answer"] + "\n\n— sources —")
    seen = set()
    for i, h in enumerate(res["sources"], 1):
        tag = f"{h['source']} · {h['title']}"
        if tag in seen:
            continue
        seen.add(tag)
        print(f"  [{i}] {tag}")
    print()


def cmd_ask(args):
    cfg = _cfg(args)
    if getattr(args, "profile", None):
        cfg = cfg.with_profile(args.profile)
    if args.question:
        _show(cfg, " ".join(args.question))
        return
    print("Deskworks — ask about your library (Ctrl-C to quit).")
    try:
        while True:
            q = input("\n? ").strip()
            if q:
                _show(cfg, q)
    except (KeyboardInterrupt, EOFError):
        print("\nbye")


def cmd_web(args):
    from . import web
    web.run(_cfg(args))


def cmd_summarize(args):
    from .summarize import summarize_folder
    summarize_folder(_cfg(args), args.folder, args.name)


def cmd_dashboard(args):
    from .dashboard import build_dashboard
    out = build_dashboard(_cfg(args), args.csv, args.out)
    print(f"Wrote {out} — open it in a browser.")


def cmd_service(args):
    """Master on/off for the always-on service (launchd on macOS, systemd on Linux).
    `off` stops everything and disables autostart; `on` brings it back."""
    import subprocess
    action = args.action
    if sys.platform == "darwin":
        plist = os.path.expanduser("~/Library/LaunchAgents/com.deskworks.brain.plist")
        if not os.path.exists(plist):
            print("No service installed. Copy service/com.deskworks.brain.plist.example to\n"
                  f"  {plist}\nedit the REPLACE_ME paths, then run:  deskworks service on")
            return
        if action == "on":
            subprocess.run(["launchctl", "load", "-w", plist])
            print("Service ON — autostarts at login. Chat: see [web] port in your config.")
        elif action == "off":
            subprocess.run(["launchctl", "unload", "-w", plist])
            print("Service OFF — stopped and won't autostart until `deskworks service on`.")
        else:
            r = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
            up = "com.deskworks.brain" in r.stdout
            print(f"Service: {'RUNNING' if up else 'stopped'}")
    elif sys.platform.startswith("linux"):
        unit = "deskworks.service"
        cmds = {"on": ["systemctl", "--user", "enable", "--now", unit],
                "off": ["systemctl", "--user", "disable", "--now", unit],
                "status": ["systemctl", "--user", "--no-pager", "status", unit]}
        subprocess.run(cmds[action])
    else:
        print(f"Service control not supported on {sys.platform}.")


def cmd_status(args):
    cfg = _cfg(args)
    print(f"Deskworks {__version__}")
    print(f"  config:   {cfg.source or '(defaults — no deskworks.toml found)'}")
    print(f"  corpus:   {cfg.corpus_paths() or '(none set)'}")
    print(f"  index:    {cfg.index_dir()}  "
          f"{'(built)' if os.path.exists(cfg.emb_path()) else '(NOT built — run: deskworks index)'}")
    print(f"  embed:    {cfg.embed['model']} on {cfg.embed['device']}")
    print(f"  llm:      {cfg.llm['model']} @ {cfg.llm['base_url']}")
    # ping the model endpoint
    url = cfg.llm["base_url"].rstrip("/") + "/models"
    try:
        req = urllib.request.Request(url)
        if cfg.llm.get("api_key"):
            req.add_header("Authorization", f"Bearer {cfg.llm['api_key']}")
        with urllib.request.urlopen(req, timeout=4) as r:
            ok = r.status == 200
        print(f"  model up: {'yes' if ok else 'no'} ({url})")
    except Exception as e:
        print(f"  model up: NO — {e}\n            start your model server (e.g. `ollama serve`).")


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(prog="deskworks", description="Private, local AI over your own documents.")
    p.add_argument("-c", "--config", help="path to deskworks.toml")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="write a starter deskworks.toml").set_defaults(fn=cmd_init)
    sub.add_parser("ingest", help="extract + cache PDF text").set_defaults(fn=cmd_ingest)
    sub.add_parser("index", help="build the hybrid search index").set_defaults(fn=cmd_index)

    a = sub.add_parser("ask", help="ask a question"); a.add_argument("question", nargs="*")
    a.add_argument("--profile", help="model profile from [llm.profiles.*]"); a.set_defaults(fn=cmd_ask)
    sub.add_parser("web", help="start the browser chat").set_defaults(fn=cmd_web)

    sv = sub.add_parser("service", help="master on/off for the always-on service")
    sv.add_argument("action", choices=["on", "off", "status"]); sv.set_defaults(fn=cmd_service)

    s = sub.add_parser("summarize", help="bulk local summaries of a folder")
    s.add_argument("folder"); s.add_argument("name"); s.set_defaults(fn=cmd_summarize)

    d = sub.add_parser("dashboard", help="build searchable HTML from a summaries CSV")
    d.add_argument("csv"); d.add_argument("--out"); d.set_defaults(fn=cmd_dashboard)

    sub.add_parser("status", help="show config + reachability").set_defaults(fn=cmd_status)

    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
