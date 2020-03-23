from flask import Flask, flash, request, render_template, redirect, Markup
from enum import Enum
import logging
from ardsnet import Vent, ARDSNet, Gender, Unit, Patient

app = Flask(__name__)
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True


class Oxygen(Enum):
    SPO2 = "spo2"
    PAO2 = "pao2"


class Volume(Enum):
    ML = "ml"
    MLKG = "mlkg"


@app.route("/")
def flaskMain():
    return render_template("main.j2", gender=Gender.Male.value, unit=Unit.Inch.value, strategy="lowpeep", o2type=Oxygen.PAO2.value, vttype=Volume.ML.value)


@app.route("/", methods=['POST'])
def flaskMainPost():
    gender = request.form.get('gender', Gender.Male, type=Gender)
    height = request.form.get('height', type=float)
    unit = request.form.get('unit', Unit.Inch, type=Unit)
    patient = None
    if gender and height and unit:
        patient = Patient(gender, height, unit)

    vt = request.form.get('vt', type=float)
    vttype = request.form.get('vttype', Volume.ML, type=Volume)
    if vttype == Volume.ML and patient:
        vt = vt / patient.pbw

    rr = request.form.get('rr', type=int)
    fio2 = request.form.get('fio2', type=float)
    peep = request.form.get('peep', type=int)

    o2 = request.form.get('o2', type=float)
    o2type = request.form.get('o2type', Oxygen.PAO2, type=Oxygen)
    if o2type == Oxygen.SPO2:
        o2 = ARDSNet.spo2ToPaO2(o2)

    pplat = request.form.get('pplat', type=float)
    ph = request.form.get('ph', type=float)
    strategy = request.form.get('strategy')

    current = Vent(vt, rr, fio2, peep)
    ards = ARDSNet(current)
    ards.adjustVent(ph, o2, pplat, hp=(strategy == 'highpeep'))

    if patient:
        absvt = ards.vent.vt * patient.pbw
    else:
        absvt = 0

    newvt = ards.vent.vt
    if vttype == Volume.ML:
        newvt = newvt * patient.pbw

    return render_template(
        "main.j2",
        vent=ards.vent,
        vt=round(newvt, 2),
        vttype=vttype.value,
        o2type=o2type.value,
        rr=ards.vent.rr,
        fio2=round(ards.vent.fio2 * 100),
        peep=ards.vent.peep, new=ards.vent,
        old=current,
        strategy=strategy,
        patient=patient,
        gender=gender.value,
        height=height,
        unit=unit.value,
        absvt=absvt
    )
