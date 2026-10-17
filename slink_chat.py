"""Streamlink Chat — les chats Twitch, Kick et Steam TV (même chose que : slink_launcher.py --chat).

Lancer avec :  pythonw slink_chat.py [lien ou --open twitch:chaîne]
"""
import sys

from chat.app import main, targets_from_argv

if __name__ == "__main__":
    main(targets_from_argv(sys.argv[1:]))
