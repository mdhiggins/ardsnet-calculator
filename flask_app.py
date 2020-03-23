from flask import Flask, flash, request, render_template, redirect, Markup
from enum import Enum
import logging
from ardsnet import Vent, ARDSNet, Gender, Patient

app = Flask(__name__)
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True
app.secret_key = b'_5#y2asdfasdfL"F4Q8zdfs]/'


class Oxygen(Enum):
    SpO2 = "spo2"
    PaO2 = "pao2"


class Volume(Enum):
    Ml = "ml"
    MlKg = "mlkg"


class WeightUnit(Enum):
    Kg = "kg"
    Lbs = "lbs"


class HeightUnit(Enum):
    Centimeter = "cm"
    Inch = "in"


def verboseOutput(oldvent, newvent, strategy, pbw, o2, pplat, ph):
    strategy = "Lower Peep Higher FiO2" if strategy == "lowpeep" else "Higher Peep Lower FiO2"
    pbw = pbw or 0.0
    if newvent == oldvent:
        base = "Maintaining vent settings %s based on ARDSNet protocol with " % (oldvent)
    else:
        base = "Changing vent settings from %s to %s based on ARDSNet protocol with " % (oldvent, newvent)

    if ph:
        base = "%s pH %0.02f, " % (base[:-1], ph)
    if o2:
        base = "%s PaO2 %d, " % (base[:-1], o2)
    if pplat:
        base = "%s Pplat %d, " % (base[:-1], pplat)
    if pbw:
        base = "%s with IBW %0.02f, " % (base[:-1], pbw)

    base = "%s %s strategy" % (base[:-1], strategy)

    return base


def safeRound(value, place=0):
    try:
        return round(value, place)
    except:
        return None


@app.route("/")
def flaskMain():
    return render_template(
        "main.j2",
        gender=Gender.Male.value,
        heightunit=HeightUnit.Inch.value,
        weightunit=WeightUnit.Kg.value,
        strategy="highpeep",
        o2type=Oxygen.PaO2.value,
        vttype=Volume.Ml.value
    )


@app.route("/", methods=['POST'])
def flaskMainPost():
    # Get PBW
    pbw = request.form.get('pbw', type=float)
    weightunit = request.form.get('weightunit', WeightUnit.Kg, type=WeightUnit)

    # Calculate PBW
    gender = request.form.get('gender', Gender.Male, type=Gender)
    heightraw = request.form.get('height', type=float)
    heightunit = request.form.get('heightunit', HeightUnit.Inch, type=HeightUnit)

    # Vent settings
    vt = request.form.get('vt', type=float)
    vttype = request.form.get('vttype', Volume.Ml, type=Volume)
    rr = request.form.get('rr', type=int)
    fio2 = request.form.get('fio2', type=float)
    peep = request.form.get('peep', type=int)

    # Current status settings
    o2 = request.form.get('o2', type=float)
    o2type = request.form.get('o2type', Oxygen.PaO2, type=Oxygen)
    pplat = request.form.get('pplat', type=float)
    ph = request.form.get('ph', type=float)
    strategy = request.form.get('strategy')

    # Conver to inches
    height = heightraw
    if heightunit == HeightUnit.Centimeter:
        height = height / 2.54

    if not pbw and gender and height:
        patient = Patient(gender, height)
        pbw = patient.pbw

    # Probably already in ml/kg
    if vttype == Volume.Ml and vt < 20:
        vttype = Volume.MlKg
        flash("Absolute tidal volume was very low, assuming you mean ml/kg not ml", "info")
    if vttype == Volume.MlKg and vt > 20:
        vttype = Volume.Ml
        flash("Weight based tidal volume was very high, assuming you mean ml not ml/kg", "info")

    # Check for incompatible values
    bad = False
    if vttype == Volume.Ml and not pbw:
        flash("If using an absolute tidal volume a predicted body weight must be provided or calculated", "danger")
        bad = True

    if not o2 and not pplat and not ph:
        flash("You did not enter any new data, no new vent changes will be recommended", "warning")
        bad = True

    # FiO2
    if fio2 > 1:
        fio2 = fio2 / 100

    # Convert VT to weight based
    vtraw = vt
    if vttype == Volume.Ml and pbw:
        vt = vt / pbw

    if round(vt) > 8 or round(vt) < 4:
        flash("Tidal volumes outside ARDSNet range and recommendations may be inaccurate", "warning")

    if bad:
        return render_template(
            "main.j2",
            gender=gender.value,
            heightunit=heightunit.value,
            weightunit=weightunit.value,
            strategy=strategy,
            vttype=vttype.value,
            o2type=o2type.value,
            vt=safeRound(vtraw, 2),
            rr=rr,
            fio2=safeRound(fio2 * 100),
            peep=peep,
            pbw=pbw,
            height=safeRound(heightraw, 2),
            o2=o2,
            pplat=pplat,
            ph=ph
        )

    # Oxygen unit conversion
    lasto2 = o2
    if o2type == Oxygen.SpO2:
        o2 = ARDSNet.spo2ToPaO2(o2)

    # Recommendations
    if ph and ph < ARDSNet.__PH_MIN__ and rr and rr == ARDSNet.__RR_MAX__:
        flash("pH very low. Consider metabolic causes. Vt may be increased in 1 ml/kg steps until pH >7.15 (Pplat target of 30 may be exceeded). May give NaHCO3", "danger")
    if pplat and pplat > ARDSNet.__PPLAT_MAX__:
        flash("Plateau pressures elevated. Consider more sedation or paralysis if vent adjustments are failing to improve pressures", "warning")
    if o2 and ph and fio2 and peep and o2 > ARDSNet.__PAO2_MAX__ and ph > ARDSNet.__PH_GOAL_MIN__ and ((fio2 <= 0.4 and peep <= 8 and rr) or (fio2 <= 0.5 and peep <= 5)):
        flash("Vent settings improving from oxygenation standpoint, reviewing weaning section of ARDSNet card", "success")

    oldvent = Vent(vt, rr, fio2, peep)
    ards = ARDSNet(oldvent)
    newvent = ards.adjustVent(ph, o2, pplat, hp=(strategy == 'highpeep'))

    # If PBW is specified, include this in output
    if pbw:
        absvt = ards.vent.vt * pbw
    else:
        absvt = 0

    # Keep the same tidal volume format for output
    newvt = ards.vent.vt
    if vttype == Volume.Ml and pbw:
        newvt = newvt * pbw

    verbose = verboseOutput(oldvent, newvent, strategy, pbw, o2, pplat, ph)

    return render_template(
        "main.j2",
        gender=gender.value,
        heightunit=heightunit.value,
        weightunit=weightunit.value,
        strategy=strategy,
        vttype=vttype.value,
        o2type=o2type.value,
        vent=ards.vent,
        vt=safeRound(newvt, 0),
        rr=ards.vent.rr,
        fio2=safeRound(ards.vent.fio2 * 100),
        peep=ards.vent.peep,
        new=newvent,
        old=oldvent,
        pbw=safeRound(pbw, 2),
        height=safeRound(heightraw, 2),
        absvt=absvt,
        verbose=verbose,
        lastph=ph,
        lasto2=lasto2,
        lastpplat=pplat
    )
