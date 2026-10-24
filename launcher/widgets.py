"""Composants dessinés sur des Canvas Tk : peu d'objets, aucune image externe, aucune dépendance.

Components drawn on Tk Canvases: few objects, no external image, no dependency.

Les composants sont rangés par famille dans les modules widgets_* ; ce module les réexporte tous,
pour que `from .widgets import Button` continue de fonctionner.

The components are grouped by family in the widgets_* modules; this module re-exports them all,
so that `from .widgets import Button` keeps working."""
from .widgets_base import Widget, _flush_redraws, _is_inside, _schedule_redraw
from .widgets_cards import Card, DrawerBar, ListRow, RecentRow, StatusCard, StreamRow
from .widgets_controls import Button, IconButton, Pill, Segmented, Select, Switch
from .widgets_field import Field, Popover, SuggestionList, draw_rows
from .widgets_layout import ScrollArea, ThinScrollbar, Toast

__all__ = [
    "_schedule_redraw",
    "_flush_redraws",
    "Widget",
    "_is_inside",
    "Button",
    "IconButton",
    "Pill",
    "Select",
    "Segmented",
    "Switch",
    "Card",
    "RecentRow",
    "ListRow",
    "StreamRow",
    "DrawerBar",
    "StatusCard",
    "Field",
    "Popover",
    "draw_rows",
    "SuggestionList",
    "ThinScrollbar",
    "ScrollArea",
    "Toast",
]
