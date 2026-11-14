"""Claude Buddy - parametric enclosure for Autodesk Fusion (Python API script).

Run in Fusion: Utilities > Scripts and Add-Ins > "+" > select the folder
cad/ClaudeBuddy > Run.  The script builds one NEW design document per variant
in BUILD_VARIANTS and exports each to export/<variant folder>/:

  Variant A "ClaudeBuddy_A_Lightbox" (2 colours: translucent orange + black)
    Body       - light box: pixel-art "Clawd" silhouette with a thin front
                 diffuser (front_t) over the whole front, open at the back.
  Variant B "ClaudeBuddy_B_WhiteFront" (2 colours: white + black)
    FrontPlate - white flat diffuser plate (silhouette + legs) with a locating
                 rim on its back; prints fused with the Housing or glues in.
    Housing    - black opaque light box behind the plate.
  Both variants:
    Eye_L      - dark eye insert, viewer's left  (+X side), black PLA
    Eye_R      - dark eye insert, viewer's right (-X side), black PLA
    BackCover  - removable back cover: carries both WS2812B strip pieces
                 (shallow seats on its inner face, LEDs facing the front),
                 wire channels, a slot that takes the ESP's rear PCB edge
                 (rear stop), an exact stadium-shaped USB-C hole,
                 4x M2 counterbored screw holes into corner bosses.

    The ESP32-C3 Super Mini lies in a pocket in the floor (components up,
    USB-C at the back, receptacle flush with the inner face of the cover).

Coordinate system (already the print orientation of the Body):
    X = width, Y = height (Y=0 is the flat underside / tape surface),
    Z = depth, Z=0 is the FRONT face (printed face-down on the plate),
    +Z points to the back (USB-C exits at the back through the cover).
    Seen from the front (viewer looks along +Z), +X is the viewer's LEFT.

Parametric behaviour:
    All key dimensions are User Parameters (Modify > Change Parameters).
    Every depth (Z) value - extrude distances and offset planes - is driven by
    parameter expressions and updates live.  Outline (X/Y) geometry is
    computed by this script from the parameters; after changing X/Y
    parameters (px, eye_*, Led*, esp_*, ...) simply run the script again while
    the modified design is active - it copies all ClaudeBuddy parameters
    (expressions) from the active design into the newly built model.

The pure-Python part (PARAMS, evaluate_defaults, layout) has no Fusion
dependency and is reused by cad/preview/render_preview.py.
"""

import math
import os
import re
import traceback

try:  # Fusion runtime
    import adsk.core
    import adsk.fusion
except ImportError:  # plain Python (preview script)
    adsk = None


# ---------------------------------------------------------------------------
# Parameters: (name, default expression, comment).  Order matters (later ones
# may reference earlier ones).  All are lengths in mm.
# ---------------------------------------------------------------------------
PARAMS = [
    # --- pixel-art silhouette (Clawd: 12 px body, 2 px arms, 4 legs) ---
    ("px", "3.75 mm", "Pixel width of the pixel-art grid (16 px overall width = 60 mm)"),
    ("body_w", "12 * px", "Body width (without arms)"),
    ("body_h", "8 * px", "Body height (Y=0 is the flat tape surface)"),
    ("arm_len", "2 * px", "Arm nub length per side"),
    ("arm_h", "2 * px", "Arm nub height"),
    ("arm_y", "2 * px", "Arm nub lower edge above the underside"),
    ("leg_w", "px", "Leg width"),
    ("leg_len", "2 * px", "Leg length below the underside (hangs over the bezel)"),
    ("leg_depth", "3 mm", "Leg thickness (Z) - legs only in the front slab"),
    ("leg_x_inner", "2.5 * px", "Center X of the inner legs"),
    ("leg_x_outer", "4.5 * px", "Center X of the outer legs"),
    # --- light box walls ---
    ("front_t", "1.2 mm", "Front diffuser thickness (whole front glows)"),
    ("wall", "2 mm", "Side/top wall thickness (thicker = less side glow)"),
    ("floor_t", "2.4 mm", "Bottom wall thickness (ESP pocket is cut into it)"),
    # --- eyes (dark inserts) ---
    ("rim_h", "1 mm", "Variant B: locating rim on the back of the FrontPlate (height)"),
    ("rim_w", "1 mm", "Variant B: locating rim wall thickness"),
    ("rim_clr", "0.15 mm", "Variant B: rim clearance to the housing walls"),
    ("eye_w", "px", "Eye width"),
    ("eye_h", "2 * px", "Eye height"),
    ("eye_cx", "3.5 * px", "Eye center distance from the middle (X)"),
    ("eye_cy", "5 * px", "Eye center height (Y)"),
    ("eye_t", "front_t + 0.8 mm", "Eye insert depth (through the diffuser + 0.8 mm into the box)"),
    # --- LED strip pieces (WS2812B 60/m, one LED each) on the back cover ---
    ("LedPcbW", "10 mm", "LED strip piece width"),
    ("LedPcbL", "16.7 mm", "LED strip piece length (pitch 60/m)"),
    ("LedPcbT", "2 mm", "LED strip piece thickness incl. 5050 LED"),
    ("LedClr", "0.3 mm", "Clearance around the LED piece (per side)"),
    ("led_cx", "9.8 mm", "LED piece center |X| (pieces lie horizontally)"),
    ("led_cy", "body_h / 2 + 2 mm", "LED piece center height (Y)"),
    ("led_seat_d", "0.4 mm", "LED seat recess depth in the cover inner face"),
    ("wire_ch_w", "3 mm", "Wire channel width in the cover (LED -> ESP)"),
    # --- ESP32-C3 Super Mini (floor pocket, components up, USB-C at the back) ---
    ("esp_l", "22.52 mm", "ESP32-C3 Super Mini PCB length (datasheet drawing)"),
    ("esp_w", "18 mm", "ESP32-C3 Super Mini PCB width"),
    ("esp_clr", "0.3 mm", "ESP pocket clearance per side (X)"),
    ("esp_pcb_t", "1 mm", "ESP PCB thickness (= pocket depth, PCB top flush with floor)"),
    ("esp_comp_h", "3.3 mm", "Tallest ESP top-side part (USB-C receptacle) above PCB top"),
    ("esp_front_wall", "1.6 mm", "Floor pocket front wall (backstop) behind the diffuser"),
    ("pad_relief_w", "1.5 mm", "Extra pocket width beside the castellated pin rows (solder)"),
    ("pad_free_end", "1.2 mm", "Pad-free length at both board ends (pocket keeps esp_clr there)"),
    ("cover_t", "2 mm", "Back cover plate thickness (receptacle front is flush with its outer face)"),
    ("recept_w", "8.94 mm", "USB-C receptacle width"),
    ("recept_h", "3.26 mm", "USB-C receptacle height"),
    ("recept_l", "7.3 mm", "USB-C receptacle length"),
    ("usb_c_h", "recept_h / 2", "USB-C receptacle center above ESP PCB top"),
    ("usb_overhang", "0.8 mm", "USB-C receptacle front past the PCB rear edge (0.5..1)"),
    ("usb_out_gap", "0 mm", "Receptacle front set back from the cover OUTER face (0 = flush)"),
    ("usb_clr", "0.2 mm", "USB-C hole clearance per side around the receptacle"),
    ("usb_w", "recept_w + 2 * usb_clr", "USB-C hole width (stadium)"),
    ("usb_h", "recept_h + 2 * usb_clr", "USB-C hole height (stadium)"),
    ("usb_r", "usb_h / 2", "USB-C hole end radius (fully rounded)"),
    ("slot_clr", "0.2 mm", "Axial play ESP PCB rear edge -> slot floor in the cover (rear stop)"),
    ("slot_top", "0.6 mm", "Cover slot height above the PCB top (parts at the board edge)"),
    ("body_depth", "front_t + esp_front_wall + esp_l + usb_overhang + usb_out_gap - cover_t",
     "Body depth without cover (derived: ESP from the pocket wall to the outer back face)"),
    # --- back cover / screws (4x M2 self-tapping into corner bosses) ---
    ("lip_depth", "2 mm", "Locating lip depth into the body"),
    ("lip_w", "1.6 mm", "Locating lip wall thickness"),
    ("lip_clr", "0.25 mm", "Lip clearance to the body walls"),
    ("boss", "5 mm", "Corner screw boss size (square)"),
    ("boss_len", "10 mm", "Corner screw boss length from the back face"),
    ("pilot_d", "1.7 mm", "Pilot hole for M2 self-tapping screw"),
    ("pilot_depth", "9 mm", "Pilot hole depth"),
    ("screw_clear_d", "2.3 mm", "Screw clearance hole in the cover"),
    ("cbore_d", "4.3 mm", "Counterbore diameter (M2 pan/cheese head)"),
    ("cbore_depth", "1 mm", "Counterbore depth"),
]

PARAM_NAMES = [p[0] for p in PARAMS]


def evaluate_defaults(overrides=None):
    """Evaluate the parameter expressions in plain Python (mm)."""
    vals = {}
    for name, expr, _ in PARAMS:
        e = (overrides or {}).get(name, expr)
        e = re.sub(r"\bmm\b", "", e)
        vals[name] = float(eval(e, {"__builtins__": {}}, dict(vals)))
    return vals


def _rect(x0, y0, x1, y1):
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _inside(a, b, eps=1e-6):
    """rect a inside rect b"""
    return a[0] >= b[0] - eps and a[1] >= b[1] - eps and a[2] <= b[2] + eps and a[3] <= b[3] + eps


def _overlap(a, b, eps=1e-6):
    return a[0] < b[2] - eps and b[0] < a[2] - eps and a[1] < b[3] - eps and b[1] < a[3] - eps


def layout(v):
    """Compute all outline geometry (mm) from parameter values (mm)."""
    L = {"warnings": [], "notes": []}
    W, H = v["body_w"], v["body_h"]
    hw = W / 2.0
    al, ay, ah = v["arm_len"], v["arm_y"], v["arm_h"]
    w, ft = v["wall"], v["floor_t"]

    L["silhouette"] = [
        (-hw, 0), (hw, 0), (hw, ay), (hw + al, ay), (hw + al, ay + ah), (hw, ay + ah),
        (hw, H), (-hw, H), (-hw, ay + ah), (-hw - al, ay + ah), (-hw - al, ay), (-hw, ay),
    ]
    L["overall_w"] = W + 2 * al

    lw = v["leg_w"]
    L["legs"] = [_rect(cx - lw / 2, -v["leg_len"], cx + lw / 2, 0.5)
                 for cx in (-v["leg_x_outer"], -v["leg_x_inner"], v["leg_x_inner"], v["leg_x_outer"])]

    # light box cavity = silhouette inset by the walls (arms are hollow too)
    ix0, iy0, ix1, iy1 = -hw + w, ft, hw - w, H - w
    L["interior"] = (ix0, iy0, ix1, iy1)
    def cavity(d=0.0):  # cavity outline, optionally inset by d
        a0, a1, b0, b1 = ix1 - d, hw + al - w - d, ay + w + d, ay + ah - w - d
        y0, y1 = iy0 + d, iy1 - d
        return [(-a0, y0), (a0, y0), (a0, b0), (a1, b0), (a1, b1), (a0, b1),
                (a0, y1), (-a0, y1), (-a0, b1), (-a1, b1), (-a1, b0), (-a0, b0)]
    L["cavity"] = cavity()
    # Variant B: locating rim on the back of the FrontPlate (ring inside the cavity)
    L["rim_outer"] = cavity(v["rim_clr"])
    L["rim_inner"] = cavity(v["rim_clr"] + v["rim_w"])
    if ah - 2 * (w + v["rim_clr"] + v["rim_w"]) < 0.5:
        L["warnings"].append("rim does not fit into the arm cavities")
    # full front outline = silhouette + legs (FrontPlate / DXF)
    out = [L["silhouette"][0]]
    for r in sorted(L["legs"]):
        out += [(r[0], 0), (r[0], -v["leg_len"]), (r[2], -v["leg_len"]), (r[2], 0)]
    L["front_outline"] = out + L["silhouette"][1:]
    if ah - 2 * w < 1.0 or al - w < 1.0:
        L["warnings"].append("arm nubs too small to be hollow")

    # eyes (dark inserts through the diffuser)
    L["windows"] = []
    for s, name in ((1, "Eye_L"), (-1, "Eye_R")):
        cx, cy = s * v["eye_cx"], v["eye_cy"]
        L["windows"].append((name, _rect(cx - v["eye_w"] / 2, cy - v["eye_h"] / 2,
                                         cx + v["eye_w"] / 2, cy + v["eye_h"] / 2)))
    if v["eye_t"] < v["front_t"]:
        L["warnings"].append("eye_t < front_t: eyes do not go through the diffuser")

    # Z levels
    D = v["body_depth"]
    L["depth"] = D
    L["total_depth"] = D + v["cover_t"]
    L["z_pocket_front"] = v["front_t"] + v["esp_front_wall"]
    L["z_pcb_rear"] = L["z_pocket_front"] + v["esp_l"]
    L["z_usb_front"] = L["z_pcb_rear"] + v["usb_overhang"]
    L["z_cover_out"] = D + v["cover_t"]
    # the PCB's rear edge reaches into the cover: slot in the cover inner face
    L["slot_depth"] = L["z_pcb_rear"] - D + v["slot_clr"]
    L["slot_skin"] = v["cover_t"] - L["slot_depth"]
    if L["slot_depth"] > 0 and L["slot_skin"] < 0.4:
        L["warnings"].append("cover skin behind the ESP slot only %.2f mm" % L["slot_skin"])
    # LED face (5050 top) -> diffuser inner face
    L["z_led_face"] = D + v["led_seat_d"] - v["LedPcbT"]
    L["light_path"] = L["z_led_face"] - v["front_t"]

    # corner screw bosses + screws
    b = v["boss"]
    L["bosses"] = [_rect(sx * ix1, yy, sx * (ix1 - b), yy + sy * b)
                   for sx in (1, -1) for (yy, sy) in ((iy0, 1), (iy1, -1))]
    L["screws"] = [((r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0) for r in L["bosses"]]
    if v["cbore_d"] > b + 2 * w - 0.8:
        L["warnings"].append("counterbore too large for the corner")

    # LED seats on the cover (pieces lie horizontally: length along X)
    pl, pw = v["LedPcbL"] + 2 * v["LedClr"], v["LedPcbW"] + 2 * v["LedClr"]
    L["led_seats"] = [_rect(s * (v["led_cx"] - pl / 2), v["led_cy"] - pw / 2,
                            s * (v["led_cx"] + pl / 2), v["led_cy"] + pw / 2) for s in (1, -1)]
    if _overlap(L["led_seats"][0], L["led_seats"][1]):
        L["warnings"].append("LED seats overlap each other")

    # ESP floor pocket (PCB top flush with the floor surface)
    ex = v["esp_w"] / 2 + v["esp_clr"]
    L["esp_y0"] = ft - v["esp_pcb_t"]                     # PCB underside
    L["esp_pocket"] = _rect(-ex, L["esp_y0"], ex, ft + 0.5)  # XY, extruded front wall -> back
    L["esp_pad_relief"] = _rect(-(v["esp_w"] / 2 + v["pad_relief_w"]), L["esp_y0"],
                                v["esp_w"] / 2 + v["pad_relief_w"], ft + 0.5)
    L["esp_top"] = ft + v["esp_comp_h"]
    if L["esp_y0"] < 1.0:
        L["warnings"].append("outer floor under the ESP pocket < 1 mm")
    if v["esp_w"] / 2 + v["pad_relief_w"] > ix1 - b - 0.5:
        L["warnings"].append("ESP pocket runs into the corner bosses")

    # USB-C cutout centred on the receptacle
    usb_y = ft + v["usb_c_h"]
    L["usb_center"] = (0.0, usb_y)
    L["usb"] = _rect(-v["usb_w"] / 2, usb_y - v["usb_h"] / 2, v["usb_w"] / 2, usb_y + v["usb_h"] / 2)
    L["recept"] = _rect(-v["recept_w"] / 2, ft, v["recept_w"] / 2, ft + v["recept_h"])
    if L["usb"][1] < 1.0:   # less than ~1 mm rim -> clean notch open at the bottom edge
        L["usb_cut"] = _rect(L["usb"][0], -v["usb_h"], L["usb"][2], L["usb"][3])
        L["notes"].append("USB-C hole is a notch open at the cover's bottom edge")
    else:
        L["usb_cut"] = L["usb"]
        L["notes"].append("USB-C hole is closed: %.2f mm rim below it" % L["usb"][1])
    # slot for the PCB's rear edge in the cover inner face (its floor is the rear stop)
    L["esp_slot"] = _rect(-ex, L["esp_y0"] - v["slot_clr"], ex, ft + v["slot_top"])

    # cover lip (around the main body interior) and its reliefs
    c = v["lip_clr"]
    L["lip_outer"] = (ix0 + c, iy0 + c, ix1 - c, iy1 - c)
    c2 = c + v["lip_w"]
    L["lip_inner"] = (ix0 + c2, iy0 + c2, ix1 - c2, iy1 - c2)
    for r in L["led_seats"]:
        if not _inside(r, L["lip_inner"]):
            L["warnings"].append("LED seat collides with the cover lip")
    # wire channels: from the outer LED ends down to the floor, outside the ESP pocket
    wx0 = v["esp_w"] / 2 + v["pad_relief_w"] + 0.5
    L["wire_channels"] = [_rect(s * wx0, ft - 0.5, s * (wx0 + v["wire_ch_w"]),
                                v["led_cy"] - pw / 2 + 2.0) for s in (1, -1)]
    lrx = wx0 + v["wire_ch_w"] + 0.3
    L["lip_reliefs"] = [_rect(-lrx, -1.0, lrx, L["esp_top"] + 1.5)]
    L["lip_reliefs"] += [(r[0] - 0.4, r[1] - 0.4, r[2] + 0.4, r[3] + 0.4) for r in L["bosses"]]
    for r in L["wire_channels"]:
        for bb in L["bosses"]:
            if _overlap(r, bb):
                L["warnings"].append("wire channel runs into a corner boss")
    for r in L["led_seats"]:
        for bb in L["bosses"]:
            if _overlap(r, bb):
                L["warnings"].append("LED seat overlaps a corner boss")
    if L["light_path"] < 12:
        L["warnings"].append("light path only %.1f mm - glow will be patchy" % L["light_path"])
    for wv, n in ((v["wall"], "wall"), (v["floor_t"], "floor_t")):
        if wv < 1.6:
            L["warnings"].append("%s < 1.6 mm (walls will glow)" % n)
    return L


# ---------------------------------------------------------------------------
# Fusion part
# ---------------------------------------------------------------------------
def _cm(mm):
    return mm / 10.0


class Builder(object):
    def __init__(self, design):
        self.design = design
        self.root = design.rootComponent
        self.planes = {}

    # ----- helpers -----
    def vi(self, expr):
        return adsk.core.ValueInput.createByString(expr)

    def plane(self, expr, name):
        if expr is None:
            return self.root.xYConstructionPlane
        if name in self.planes:
            return self.planes[name]
        pi = self.root.constructionPlanes.createInput()
        pi.setByOffset(self.root.xYConstructionPlane, self.vi(expr))
        pl = self.root.constructionPlanes.add(pi)
        pl.name = name
        self.planes[name] = pl
        return pl

    def sketch(self, plane, name):
        sk = self.root.sketches.add(plane)
        sk.name = name
        return sk

    def pt(self, sk, x, y):
        p = sk.modelToSketchSpace(adsk.core.Point3D.create(_cm(x), _cm(y), 0))
        return adsk.core.Point3D.create(p.x, p.y, 0)

    def rect(self, sk, r):
        x0, y0, x1, y1 = r
        sk.sketchCurves.sketchLines.addTwoPointRectangle(self.pt(sk, x0, y0), self.pt(sk, x1, y1))

    def rounded_rect(self, sk, r, rad):
        x0, y0, x1, y1 = r
        rad = min(rad, (x1 - x0) / 2.0, (y1 - y0) / 2.0)
        if rad <= 0.05:
            return self.rect(sk, r)
        lines = sk.sketchCurves.sketchLines
        arcs = sk.sketchCurves.sketchArcs
        P = lambda x, y: self.pt(sk, x, y)
        eps = 1e-4
        if x1 - x0 - 2 * rad > eps:
            lines.addByTwoPoints(P(x0 + rad, y0), P(x1 - rad, y0))
            lines.addByTwoPoints(P(x1 - rad, y1), P(x0 + rad, y1))
        if y1 - y0 - 2 * rad > eps:   # (a full stadium has no straight vertical sides)
            lines.addByTwoPoints(P(x1, y0 + rad), P(x1, y1 - rad))
            lines.addByTwoPoints(P(x0, y1 - rad), P(x0, y0 + rad))
        h = rad * (1 - math.sqrt(0.5))
        for (cx, cy, sx, sy) in ((x1, y0, -1, 1), (x1, y1, -1, -1), (x0, y1, 1, -1), (x0, y0, 1, 1)):
            a = P(cx + sx * rad, cy)
            m = P(cx + sx * h, cy + sy * h)
            b = P(cx, cy + sy * rad)
            arcs.addByThreePoints(a, m, b)

    def circle(self, sk, x, y, d):
        sk.sketchCurves.sketchCircles.addByCenterRadius(self.pt(sk, x, y), _cm(d / 2.0))

    def polygon(self, sk, pts):
        lines = sk.sketchCurves.sketchLines
        first = lines.addByTwoPoints(self.pt(sk, *pts[0]), self.pt(sk, *pts[1]))
        prev = first
        for p in pts[2:]:
            prev = lines.addByTwoPoints(prev.endSketchPoint, self.pt(sk, *p))
        lines.addByTwoPoints(prev.endSketchPoint, first.startSketchPoint)

    def all_profiles(self, sk):
        coll = adsk.core.ObjectCollection.create()
        for i in range(sk.profiles.count):
            coll.add(sk.profiles.item(i))
        if coll.count == 0:
            raise RuntimeError("Sketch '%s' has no closed profile" % sk.name)
        return coll

    def ring_profile(self, sk):
        for i in range(sk.profiles.count):
            p = sk.profiles.item(i)
            if p.profileLoops.count == 2:
                return p
        raise RuntimeError("No ring profile in sketch '%s'" % sk.name)

    def body(self, name):
        b = self.root.bRepBodies.itemByName(name)
        if b is None:
            raise RuntimeError("Body '%s' not found" % name)
        return b

    def extrude(self, profiles, expr, op, participants=None, name=None):
        ex = self.root.features.extrudeFeatures
        inp = ex.createInput(profiles, op)
        inp.setDistanceExtent(False, self.vi(expr))
        if participants:
            inp.participantBodies = [self.body(n) for n in participants]
        f = ex.add(inp)
        if name:
            f.name = name
        return f


def _setup_parameters(design, source_exprs):
    ups = design.userParameters
    for name, expr, comment in PARAMS:
        e = source_exprs.get(name, expr)
        existing = ups.itemByName(name)
        try:
            if existing:
                existing.expression = e
            else:
                ups.add(name, adsk.core.ValueInput.createByString(e), "mm", comment)
        except Exception:
            # fall back to the default expression if the copied one fails
            if existing:
                existing.expression = expr
            else:
                ups.add(name, adsk.core.ValueInput.createByString(expr), "mm", comment)
    return dict((name, ups.itemByName(name).value * 10.0) for name in PARAM_NAMES)  # cm -> mm


def _read_existing_expressions(app):
    exprs = {}
    try:
        des = adsk.fusion.Design.cast(app.activeProduct)
        if des and des.userParameters.itemByName("px"):
            for name in PARAM_NAMES:
                p = des.userParameters.itemByName(name)
                if p:
                    exprs[name] = p.expression
    except Exception:
        pass
    return exprs


# Fusion appearance library + "Plastic - Matte (...)" appearances, looked up by
# id so that it also works with a non-English Fusion UI (names are localized).
_APPEARANCE_LIB_ID = "BA5EE55E-9982-449B-9D66-9F036540E140"
_PLASTIC_MATTE_IDS = ("Prism-129", "Prism-127", "Prism-128", "Prism-126")  # yellow/white, matte/glossy


def _try_color(app, design, body, rgb, opacity=None):
    """Purely cosmetic - never raises.  Returns a status string."""
    try:
        lib = app.materialLibraries.itemById(_APPEARANCE_LIB_ID)
        if lib is None:
            for i in range(app.materialLibraries.count):
                l = app.materialLibraries.item(i)
                if "Appearance" in l.name or "Darstellung" in l.name:
                    lib = l
                    break
        if lib is None:
            return "appearance library not found"
        base = None
        for cand in _PLASTIC_MATTE_IDS:
            base = lib.appearances.itemById(cand)
            if base:
                break
        if base is None:
            for cand in ("Plastic - Matte (Yellow)", "Plastic - Glossy (Yellow)"):
                base = lib.appearances.itemByName(cand)
                if base:
                    break
        if base is None:
            return "no plastic base appearance found"
        name = "ClaudeBuddy_%d_%d_%d" % rgb
        ap = design.appearances.itemByName(name)
        if ap is None:
            ap = design.appearances.addByCopy(base, name)
            # the visible base color of Prism plastics is "opaque_albedo"
            cp = adsk.core.ColorProperty.cast(ap.appearanceProperties.itemById("opaque_albedo"))
            props = [cp] if cp else [adsk.core.ColorProperty.cast(ap.appearanceProperties.item(i))
                                     for i in range(ap.appearanceProperties.count)]
            for cp in props:
                if cp and not cp.isReadOnly:
                    try:
                        cp.value = adsk.core.Color.create(rgb[0], rgb[1], rgb[2], 255)
                    except Exception:
                        pass
        body.appearance = ap
        return "ok"
    except Exception as e:
        return "appearance failed: %s" % e


VARIANTS = {
    # key: (document name, export subfolder)
    "A": ("ClaudeBuddy_A_Lightbox", "A_lightbox"),      # translucent orange body, dark eyes
    "B": ("ClaudeBuddy_B_WhiteFront", "B_whitefront"),  # white front plate, black housing
}
BUILD_VARIANTS = ("A", "B")   # which variants run() builds - e.g. ("B",) for only one

# body name -> (rgb, comment) per variant (cosmetic appearance in Fusion)
COLORS = {
    "A": {"Body": (217, 119, 87), "Eye_L": (30, 30, 30), "Eye_R": (30, 30, 30), "BackCover": (217, 119, 87)},
    "B": {"FrontPlate": (245, 245, 245), "Eye_L": (30, 30, 30), "Eye_R": (30, 30, 30),
          "Housing": (35, 35, 35), "BackCover": (35, 35, 35)},
}


def build(app, ui, variant="A", source_exprs=None):
    if source_exprs is None:
        source_exprs = _read_existing_expressions(app)
    doc_name = VARIANTS[variant][0]

    doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    try:
        doc.name = doc_name
    except Exception:
        pass

    v = _setup_parameters(design, source_exprs)
    L = layout(v)
    B = Builder(design)
    NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    main = "Body" if variant == "A" else "Housing"

    xy = B.plane(None, "XY")
    p_front = B.plane("front_t", "P_FrontInner")
    p_espf = B.plane("front_t + esp_front_wall", "P_EspPocketFront")
    p_pad = B.plane("front_t + esp_front_wall + pad_free_end", "P_EspPadZone")
    p_boss = B.plane("body_depth - boss_len", "P_Boss")
    p_pilot = B.plane("body_depth - pilot_depth", "P_Pilot")
    p_back = B.plane("body_depth", "P_Back")
    p_lip = B.plane("body_depth - lip_depth", "P_Lip")
    p_cb = B.plane("body_depth + cover_t - cbore_depth", "P_Counterbore")

    # 1 Shell
    if variant == "A":
        sk = B.sketch(xy, "Silhouette")
        B.polygon(sk, L["silhouette"])
        f = B.extrude(B.all_profiles(sk), "body_depth", NEW, name="Body")
        f.bodies.item(0).name = "Body"
        sk = B.sketch(xy, "Legs")
        for r in L["legs"]:
            B.rect(sk, r)
        B.extrude(B.all_profiles(sk), "leg_depth", JOIN, ["Body"], "Legs")
    else:
        sk = B.sketch(p_front, "Silhouette")
        B.polygon(sk, L["silhouette"])
        f = B.extrude(B.all_profiles(sk), "body_depth - front_t", NEW, name="Housing")
        f.bodies.item(0).name = "Housing"
        sk = B.sketch(p_front, "Legs")
        for r in L["legs"]:
            B.rect(sk, r)
        B.extrude(B.all_profiles(sk), "leg_depth - front_t", JOIN, ["Housing"], "Legs")

    # 2 Light box cavity (open at the back, arms hollow)
    sk = B.sketch(p_front, "Cavity")
    B.polygon(sk, L["cavity"])
    B.extrude(B.all_profiles(sk), "body_depth - front_t + 1 mm", CUT, [main], "Cavity")

    # 3 Front: (B) white front plate with locating rim
    front = "Body"
    if variant == "B":
        front = "FrontPlate"
        sk = B.sketch(xy, "FrontOutline")
        B.polygon(sk, L["front_outline"])
        f = B.extrude(B.all_profiles(sk), "front_t", NEW, name="FrontPlate")
        f.bodies.item(0).name = "FrontPlate"
        sk = B.sketch(p_front, "PlateRim")
        B.polygon(sk, L["rim_outer"])
        B.polygon(sk, L["rim_inner"])
        B.extrude(B.ring_profile(sk), "rim_h", JOIN, ["FrontPlate"], "PlateRim")
        # export-only sketch: 1:1 front outline + eyes (front_outline.dxf)
        sk = B.sketch(xy, "FrontDXF")
        B.polygon(sk, L["front_outline"])
        for _, r in L["windows"]:
            B.rect(sk, r)

    # 3b Dark eye inserts (both variants): through the front diffuser, flush with the front
    sk = B.sketch(xy, "EyeWindows")
    for _, r in L["windows"]:
        B.rect(sk, r)
    B.extrude(B.all_profiles(sk), "eye_t", CUT, [front], "EyeWindows")
    for name, r in L["windows"]:
        sk = B.sketch(xy, name)
        B.rect(sk, r)
        f = B.extrude(B.all_profiles(sk), "eye_t", NEW, name=name)
        f.bodies.item(0).name = name

    # 4 ESP floor pocket (front wall = backstop, open towards the back)
    sk = B.sketch(p_espf, "EspPocket")
    B.rect(sk, L["esp_pocket"])
    B.extrude(B.all_profiles(sk), "body_depth - front_t - esp_front_wall + 1 mm", CUT, [main], "EspPocket")
    # solder relief beside the castellated pin rows (pad-free ends keep the tight fit = X guides)
    sk = B.sketch(p_pad, "EspPadRelief")
    B.rect(sk, L["esp_pad_relief"])
    B.extrude(B.all_profiles(sk), "esp_l - 2 * pad_free_end", CUT, [main], "EspPadRelief")

    # 5 Corner screw bosses + pilot holes
    sk = B.sketch(p_boss, "Bosses")
    for r in L["bosses"]:
        B.rect(sk, r)
    B.extrude(B.all_profiles(sk), "boss_len", JOIN, [main], "Bosses")
    sk = B.sketch(p_pilot, "PilotHoles")
    for (x, y) in L["screws"]:
        B.circle(sk, x, y, v["pilot_d"])
    B.extrude(B.all_profiles(sk), "pilot_depth + 1 mm", CUT, [main], "PilotHoles")

    # 6 Back cover plate + locating lip (+ reliefs for ESP, wires, bosses)
    sk = B.sketch(p_back, "Cover")
    B.polygon(sk, L["silhouette"])
    f = B.extrude(B.all_profiles(sk), "cover_t", NEW, name="BackCover")
    f.bodies.item(0).name = "BackCover"
    sk = B.sketch(p_lip, "CoverLip")
    B.rect(sk, L["lip_outer"])
    B.rect(sk, L["lip_inner"])
    B.extrude(B.ring_profile(sk), "lip_depth", JOIN, ["BackCover"], "CoverLip")
    sk = B.sketch(p_lip, "LipReliefs")
    for r in L["lip_reliefs"]:
        B.rect(sk, r)
    B.extrude(B.all_profiles(sk), "lip_depth", CUT, ["BackCover"], "LipReliefs")

    # 7 LED seats (strip pieces stick to the cover, LEDs face the front) + wire channels
    sk = B.sketch(p_back, "LedSeats")
    for r in L["led_seats"]:
        B.rect(sk, r)
    B.extrude(B.all_profiles(sk), "led_seat_d", CUT, ["BackCover"], "LedSeats")
    sk = B.sketch(p_lip, "WireChannels")
    for r in L["wire_channels"]:
        B.rect(sk, r)
    B.extrude(B.all_profiles(sk), "lip_depth + led_seat_d", CUT, ["BackCover"], "WireChannels")

    # 8 Slot for the ESP's rear PCB edge (its floor = rear stop, slot_clr play)
    if L["slot_depth"] > 0:
        sk = B.sketch(p_lip, "EspSlot")
        B.rect(sk, L["esp_slot"])
        B.extrude(B.all_profiles(sk), "lip_depth + esp_front_wall + esp_l + front_t - body_depth + slot_clr",
                  CUT, ["BackCover"], "EspSlot")

    # 9 USB-C hole = receptacle outline + usb_clr, stadium shape, concentric with the receptacle
    sk = B.sketch(p_lip, "UsbCutout")
    B.rounded_rect(sk, L["usb_cut"], v["usb_r"])
    B.extrude(B.all_profiles(sk), "lip_depth + cover_t + 1 mm", CUT, ["BackCover"], "UsbCutout")

    # 10 Screw clearance holes + counterbores
    sk = B.sketch(p_back, "ScrewHoles")
    for (x, y) in L["screws"]:
        B.circle(sk, x, y, v["screw_clear_d"])
    B.extrude(B.all_profiles(sk), "cover_t + 1 mm", CUT, ["BackCover"], "ScrewHoles")
    sk = B.sketch(p_cb, "Counterbores")
    for (x, y) in L["screws"]:
        B.circle(sk, x, y, v["cbore_d"])
    B.extrude(B.all_profiles(sk), "cbore_depth + 1 mm", CUT, ["BackCover"], "Counterbores")

    # cosmetics
    for name, rgb in COLORS[variant].items():
        _try_color(app, design, B.body(name), rgb)
    for i in range(design.rootComponent.constructionPlanes.count):
        design.rootComponent.constructionPlanes.item(i).isLightBulbOn = False
    for i in range(design.rootComponent.sketches.count):
        design.rootComponent.sketches.item(i).isVisible = False
    try:
        app.activeViewport.fit()
    except Exception:
        pass
    return design, v, L


REF_NAME = "ESP32C3_SuperMini_REF"


def add_reference(app, design, v, L):
    """ESP32-C3 Super Mini reference model (not printed) in its own component,
    placed where it sits in the case: PCB against the pocket front wall,
    USB-C receptacle front flush with the outer back face."""
    root = design.rootComponent
    old = root.occurrences.itemByName(REF_NAME + ":1")
    if old:
        old.deleteMe()
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    comp = occ.component
    comp.name = REF_NAME
    tbm = adsk.fusion.TemporaryBRepManager.get()
    P3 = lambda x, y, z: adsk.core.Point3D.create(_cm(x), _cm(y), _cm(z))

    def box(x0, y0, z0, x1, y1, z1):
        c = P3((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
        ob = adsk.core.OrientedBoundingBox3D.create(c, adsk.core.Vector3D.create(1, 0, 0),
                                                    adsk.core.Vector3D.create(0, 1, 0),
                                                    _cm(abs(x1 - x0)), _cm(abs(y1 - y0)), _cm(abs(z1 - z0)))
        return tbm.createBox(ob)

    ft, y0 = v["floor_t"], L["esp_y0"]
    zf, zr, zu = L["z_pocket_front"], L["z_pcb_rear"], L["z_usb_front"]
    hw = v["esp_w"] / 2
    parts = []
    parts.append(("PCB", box(-hw, y0, zf, hw, ft, zr), (25, 25, 30)))
    # USB-C receptacle: stadium cross-section (rounded ends), overhanging the PCB edge
    rw, rh, rl = v["recept_w"], v["recept_h"], v["recept_l"]
    r = rh / 2
    cy = ft + r
    rec = box(-(rw / 2 - r), ft, zu - rl, rw / 2 - r, ft + rh, zu)
    for sx in (1, -1):
        cyl = tbm.createCylinderOrCone(P3(sx * (rw / 2 - r), cy, zu - rl), _cm(r), P3(sx * (rw / 2 - r), cy, zu), _cm(r))
        tbm.booleanOperation(rec, cyl, adsk.fusion.BooleanTypes.UnionBooleanType)
    parts.append(("USB_C", rec, (150, 150, 155)))
    # rough components (from the top view drawing: USB at the rear, buttons below it,
    # ESP32-C3 chip in the middle, ceramic antenna at the front end)
    parts.append(("Button_BOOT", box(-5.5, ft, zr - 10.0, -2.5, ft + 1.2, zr - 7.6), (60, 60, 60)))
    parts.append(("Button_RST", box(2.5, ft, zr - 10.0, 5.5, ft + 1.2, zr - 7.6), (60, 60, 60)))
    parts.append(("ESP32C3_chip", box(-2.5, ft, zr - 16.0, 2.5, ft + 0.9, zr - 11.0), (40, 40, 40)))
    parts.append(("Antenna", box(-3.0, ft, zf + 0.6, 3.0, ft + 1.2, zf + 2.2), (120, 70, 80)))
    bf = comp.features.baseFeatures.add()
    bf.startEdit()
    for name, b, rgb in parts:
        nb = comp.bRepBodies.add(b, bf)
        nb.name = name
    bf.finishEdit()
    for i in range(comp.bRepBodies.count):
        b = comp.bRepBodies.item(i)
        rgb = dict((n, c) for n, _, c in parts).get(b.name, (30, 30, 30))
        _try_color(app, design, b, rgb)
    return occ


def export_all(design, out_dir, variant=None):
    msgs = []
    try:
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
    except Exception as e:
        return ["export folder failed: %s" % e]
    em = design.exportManager
    root = design.rootComponent
    base = VARIANTS[variant][0] if variant else "ClaudeBuddy"
    ref = root.occurrences.itemByName(REF_NAME + ":1")
    if ref:
        try:
            opts = em.createSTEPExportOptions(os.path.join(out_dir, "ESP32C3_ref.step"), ref.component)
            em.execute(opts)
            msgs.append("ESP32C3_ref.step (reference only, not for printing)")
        except Exception as e:
            msgs.append("ref STEP failed: %s" % e)
        ref.isLightBulbOn = False   # printable exports must not contain the reference
    for i in range(root.bRepBodies.count):   # hidden bodies would be skipped by STEP/3MF/STL
        root.bRepBodies.item(i).isLightBulbOn = True
    try:
        opts = em.createSTEPExportOptions(os.path.join(out_dir, base + ".step"), root)
        em.execute(opts)
        msgs.append(base + ".step")
    except Exception as e:
        msgs.append("STEP failed: %s" % e)
    for i in range(root.bRepBodies.count):
        body = root.bRepBodies.item(i)
        name = body.name
        try:
            opts = em.createSTLExportOptions(body, os.path.join(out_dir, name + ".stl"))
            opts.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
            em.execute(opts)
            msgs.append(name + ".stl")
        except Exception as e:
            msgs.append("%s.stl failed: %s" % (name, e))
    try:
        opts = em.createC3MFExportOptions(root, os.path.join(out_dir, base + ".3mf"))
        em.execute(opts)
        msgs.append(base + ".3mf")
    except Exception as e:
        msgs.append("3MF failed (ok, use STEP/STL): %s" % e)
    # 1:1 front outline (silhouette + legs) + eye outlines (variant B)
    sk = root.sketches.itemByName("FrontDXF")
    if sk is not None:
        try:
            sk.saveAsDXF(os.path.join(out_dir, "front_outline.dxf"))
            msgs.append("front_outline.dxf")
        except Exception as e:
            msgs.append("DXF failed: %s" % e)
    if ref:
        ref.isLightBulbOn = True
    return msgs


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        source_exprs = _read_existing_expressions(app)
        export_root = os.path.join(os.path.dirname(os.path.realpath(__file__)), "export")
        msg = "Claude Buddy built.\n\n"
        for variant in BUILD_VARIANTS:
            design, v, L = build(app, ui, variant, source_exprs)
            add_reference(app, design, v, L)
            out_dir = os.path.join(export_root, VARIANTS[variant][1])
            try:
                exported = export_all(design, out_dir, variant)
            except Exception:
                exported = ["export failed:\n" + traceback.format_exc()]
            msg += ("%s: %.1f x %.1f (+%.1f legs) x %.1f mm (body %.1f + cover %.1f), light path %.1f mm\n"
                    "  -> %s: %s\n\n" % (VARIANTS[variant][0], L["overall_w"], v["body_h"], v["leg_len"],
                                         L["total_depth"], L["depth"], v["cover_t"], L["light_path"],
                                         out_dir, ", ".join(exported)))
        if L["notes"]:
            msg += "Notes:\n- " + "\n- ".join(L["notes"]) + "\n\n"
        if L["warnings"]:
            msg += "WARNINGS:\n- " + "\n- ".join(L["warnings"]) + "\n\n"
        ui.messageBox(msg, "Claude Buddy")
    except Exception:
        if ui:
            ui.messageBox("Claude Buddy script failed:\n%s" % traceback.format_exc(), "Claude Buddy")


if __name__ == "__main__":  # plain Python: print the evaluated layout
    vals = evaluate_defaults()
    lay = layout(vals)
    print("overall width %.2f, body %.2f x %.2f, depth %.2f (+cover %.2f), light path %.2f" % (
        lay["overall_w"], vals["body_w"], vals["body_h"], lay["depth"], lay["total_depth"], lay["light_path"]))
    for n in lay["notes"]:
        print("NOTE:", n)
    for w in lay["warnings"]:
        print("WARNING:", w)
