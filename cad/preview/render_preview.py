"""Approximate 2D preview of the Claude Buddy enclosure (no Fusion needed).

Uses the same PARAMS + layout() as the Fusion script, so dimensions match.
Run:  python3 render_preview.py   (needs matplotlib)  -> preview.png
Shows variant A (light box, translucent orange) - variant B has the same
interior, only the front is a separate white FrontPlate and the housing black.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ClaudeBuddy"))
import ClaudeBuddy as C  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Polygon, Rectangle, Circle  # noqa: E402

ORANGE, COVER, DARK = "#D97757", "#B8633F", "#262626"
LED, ESP, VOID, LIGHT = "#FFE08A", "#2E7D5B", "#FFFFFF", "#FFF4D6"

v = C.evaluate_defaults()
L = C.layout(v)
W, H, D, Dt = v["body_w"], v["body_h"], L["depth"], L["total_depth"]
XL = L["overall_w"] / 2 + 3
YL0, YL1 = -v["leg_len"] - 3, H + 4
ft, fl = v["front_t"], v["floor_t"]


def R(ax, r, **kw):
    x0, y0, x1, y1 = r
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, **kw))


def mirror_x(pts):  # front view: viewer looks along +Z, so +X is viewer's left
    return [(-x, y) for x, y in pts]


def mr(r):
    return C._rect(-r[0], r[1], -r[2], r[3])


fig, axs = plt.subplots(2, 3, figsize=(17, 10))
for ax in axs.flat:
    ax.set_aspect("equal")
    ax.grid(True, lw=0.3, alpha=0.4)

# 1 front view (as the user sees it)
ax = axs[0, 0]
ax.set_title("FRONT (user view)  %.1f x %.1f mm" % (L["overall_w"], H))
ax.add_patch(Polygon(mirror_x(L["front_outline"]), closed=True, fc=ORANGE, ec="k"))
for name, r in L["windows"]:
    R(ax, mr(r), fc=DARK, ec="k")
    ax.text(-(r[0] + r[2]) / 2, r[1] - 1.8, name, ha="center", fontsize=7)
ax.axhline(0, color="b", ls="--", lw=0.8)
ax.text(XL - 1, 0.3, "tape surface / monitor top", color="b", fontsize=7, ha="right")
ax.set_xlim(-XL, XL); ax.set_ylim(YL0, YL1)

# 2 back view (cover)
ax = axs[0, 1]
ax.set_title("BACK (cover)  USB-C hole %.2f x %.2f + 4x M2" % (v["usb_w"], v["usb_h"]))
ax.add_patch(Polygon(L["silhouette"], closed=True, fc=COVER, ec="k"))
u = L["usb_cut"]
R(ax, (u[0] + v["usb_r"], u[1], u[2] - v["usb_r"], u[3]), fc="#999", ec="none")
for xc in (u[0] + v["usb_r"], u[2] - v["usb_r"]):
    ax.add_patch(Circle((xc, (u[1] + u[3]) / 2), v["usb_r"], fc="#999", ec="none"))
ax.text(0, u[3] + 1.5, "USB-C receptacle flush", ha="center", fontsize=7)
for x, y in L["screws"]:
    ax.add_patch(Circle((x, y), v["cbore_d"] / 2, fc="#999", ec="k"))
    ax.add_patch(Circle((x, y), v["screw_clear_d"] / 2, fc=VOID, ec="k"))
R(ax, L["lip_outer"], fill=False, ec="k", ls=":")
ax.set_xlim(-XL, XL); ax.set_ylim(YL0, YL1)

# 3 cover inner face (seen from the front): LED seats, wire channels, tabs, bosses
ax = axs[0, 2]
ax.set_title("COVER inner face (seen from front): LED seats, wires, ESP")
ax.add_patch(Polygon(L["silhouette"], closed=True, fc=COVER, ec="k"))
ax.add_patch(Polygon(L["cavity"], closed=True, fc="#E9A98F", ec="k", ls=":"))
for r in L["led_seats"]:
    R(ax, r, fc=VOID, ec="k")
    x0, y0, x1, y1 = r
    R(ax, (x0 + v["LedClr"], y0 + v["LedClr"], x1 - v["LedClr"], y1 - v["LedClr"]), fc=LED, ec="#b08000")
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    R(ax, (cx - 2.5, cy - 2.5, cx + 2.5, cy + 2.5), fc="#fff", ec="#b08000")
for r in L["wire_channels"]:
    R(ax, r, fc="none", ec="r", ls="--")
for r in L["bosses"]:
    R(ax, r, fc=ORANGE, ec="k")
for x, y in L["screws"]:
    ax.add_patch(Circle((x, y), v["pilot_d"] / 2, fc=VOID, ec="k"))
R(ax, L["esp_pad_relief"], fc="none", ec=ESP, ls=":")
R(ax, (-v["esp_w"] / 2, L["esp_y0"], v["esp_w"] / 2, fl), fc=ESP, ec="k")
R(ax, L["recept"], fc="#bbb", ec="k")
R(ax, L["esp_slot"], fc="none", ec="k", ls="--")
for name, r in L["windows"]:
    R(ax, r, fc="none", ec=DARK, lw=1.2)
ax.text(0, YL0 + 1, "yellow = LED strip piece (LED faces front), red dashed = wire channel, green = ESP",
        ha="center", fontsize=6)
ax.set_xlim(-XL, XL); ax.set_ylim(YL0, YL1)

# 4 side section through the LED (x = led_cx), front at left
ax = axs[1, 0]
ax.set_title("SIDE SECTION at X=LED center - light path %.1f mm" % L["light_path"])
ax.add_patch(Polygon([(0, 0), (D, 0), (D, H), (0, H)], closed=True, fc=ORANGE, ec="k"))
R(ax, (ft, fl, D, H - v["wall"]), fc=LIGHT, ec="k")
R(ax, (0, -v["leg_len"], v["leg_depth"], 0), fc=ORANGE, ec="k")
R(ax, (D, 0, Dt, H), fc=COVER, ec="k")
R(ax, (D - v["lip_depth"], L["lip_outer"][3] - v["lip_w"], D, L["lip_outer"][3]), fc=COVER, ec="k")
sy0, sy1 = L["led_seats"][0][1], L["led_seats"][0][3]
R(ax, (L["z_led_face"] + 1.65, sy0 + v["LedClr"], D + v["led_seat_d"], sy1 - v["LedClr"]), fc=LED, ec="#b08000")
R(ax, (L["z_led_face"], v["led_cy"] - 2.5, L["z_led_face"] + 1.65, v["led_cy"] + 2.5), fc="#fff", ec="#b08000")
ax.annotate("", (ft, v["led_cy"]), (L["z_led_face"], v["led_cy"]), arrowprops=dict(arrowstyle="->", color="#b08000"))
w = L["windows"][0][1]
R(ax, (0, w[1], v["eye_t"], w[3]), fc=DARK, ec="k")
ax.axhline(0, color="b", ls="--", lw=0.8)
ax.set_xlim(-2, Dt + 4); ax.set_ylim(YL0, YL1)
ax.set_xlabel("Z (depth) mm")

# 5 center section X=0: ESP in the floor pocket, USB
ax = axs[1, 1]
ax.set_title("SIDE SECTION at X=0 (ESP32-C3 floor pocket, USB-C)")
ax.add_patch(Polygon([(0, 0), (D, 0), (D, H), (0, H)], closed=True, fc=ORANGE, ec="k"))
R(ax, (ft, fl, D, H - v["wall"]), fc=LIGHT, ec="k")
R(ax, (L["z_pocket_front"], L["esp_y0"], D, fl), fc=VOID, ec="k")
R(ax, (L["z_pocket_front"], L["esp_y0"], L["z_pcb_rear"], fl), fc=ESP, ec="k")
uy = L["usb_center"][1]
R(ax, (L["z_usb_front"] - v["recept_l"], fl, L["z_usb_front"], fl + v["recept_h"]), fc="#bbb", ec="k")
R(ax, (D, L["usb"][3], Dt, H), fc=COVER, ec="k")
R(ax, (D, 0, Dt, L["esp_slot"][1]), fc=COVER, ec="k")
R(ax, (D + L["slot_depth"], L["esp_slot"][1], Dt, L["usb"][1]), fc=COVER, ec="k")
R(ax, (Dt, uy - 3.25, Dt + 8, uy + 3.25), fc="#555", ec="k", alpha=0.5)
ax.text(Dt + 0.5, uy + 4, "USB-C plug", fontsize=7)
ax.text(L["z_pocket_front"] + 1, fl + 0.6, "ESP32-C3 Super Mini", fontsize=7, color=ESP)
ax.axhline(0, color="b", ls="--", lw=0.8)
ax.set_xlim(-2, Dt + 10); ax.set_ylim(YL0, YL1)
ax.set_xlabel("Z (depth) mm")

# 6 top view of the floor (front at bottom)
ax = axs[1, 2]
ax.set_title("FLOOR (top view, front at bottom)")
ow = L["overall_w"] / 2
R(ax, (-W / 2, 0, W / 2, D), fc=ORANGE, ec="k")
R(ax, (-ow, 0, -W / 2, D), fc=ORANGE, ec="k")
R(ax, (W / 2, 0, ow, D), fc=ORANGE, ec="k")
R(ax, (-W / 2, D, W / 2, Dt), fc=COVER, ec="k")
ix0, ix1 = L["interior"][0], L["interior"][2]
R(ax, (ix0, ft, ix1, D), fc=LIGHT, ec="k")
pr = L["esp_pad_relief"]
R(ax, (L["esp_pocket"][0], L["z_pocket_front"], L["esp_pocket"][2], D), fc=VOID, ec="k")
R(ax, (pr[0], L["z_pocket_front"] + v["pad_free_end"], pr[2], L["z_pocket_front"] + v["esp_l"] - v["pad_free_end"]), fc=VOID, ec="k")
R(ax, (-v["esp_w"] / 2, L["z_pocket_front"], v["esp_w"] / 2, L["z_pcb_rear"]), fc=ESP, ec="k", alpha=0.8)
R(ax, (-v["recept_w"] / 2, L["z_usb_front"] - v["recept_l"], v["recept_w"] / 2, L["z_usb_front"]), fc="#bbb", ec="k")
for r in L["bosses"]:
    R(ax, (r[0], D - v["boss_len"], r[2], D), fc=ORANGE, ec="k")
ax.set_xlim(-XL, XL); ax.set_ylim(-3, Dt + 3)
ax.set_xlabel("X mm (+X = viewer's left)")

fig.suptitle("Claude Buddy preview (variant A) - overall %.1f W x %.1f H (+%.1f legs) x %.1f D mm   (px = %.2f mm, light path %.1f mm)"
             % (L["overall_w"], H, v["leg_len"], Dt, v["px"], L["light_path"]))
txt = []
for n in L["notes"]:
    txt.append("note: " + n)
for w_ in L["warnings"]:
    txt.append("WARNING: " + w_)
if txt:
    fig.text(0.01, 0.01, "\n".join(txt), fontsize=8)
fig.tight_layout(rect=(0, 0.03, 1, 0.97))
fig.savefig(os.path.join(HERE, "preview.png"), dpi=110)
print("wrote", os.path.join(HERE, "preview.png"))
