"""Streamlink Launcher — point d'entrée.

Lancer avec :  pythonw slink_launcher.py   (sans console)
          ou :  python slink_launcher.py
Chats :        pythonw slink_launcher.py --chat [--open twitch:chaîne]   (Streamlink Chat, fenêtre à part)
"""
import sys

if __name__ == "__main__":
    if "--chat" in sys.argv[1:]:
        from chat.app import main, targets_from_argv
        main(targets_from_argv(sys.argv[1:]))
    else:
        from launcher.app import main
        main()
