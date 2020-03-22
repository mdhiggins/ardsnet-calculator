from flask import Flask, flash, request, render_template, redirect, Markup
from enum import Enum
import logging
from ardsnet import Vent, ARDSNet, Gender, Unit, Patient

app = Flask(__name__)
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True


@app.route("/")
def flaskMain():
    return render_template("main.j2", gender="male", unit="in", strategy="lowpeep")


@app.route("/", methods=['POST'])
def flaskMainPost():
    gender = request.form.get('gender', Gender.Male, type=Gender)
    height = request.form.get('height', type=float)
    unit = request.form.get('unit', Unit.Inch, type=Unit)
    patient = None
    if gender and height and unit:
        patient = Patient(gender, height, unit)

    vt = request.form.get('vt', type=int)
    rr = request.form.get('rr', type=int)
    fio2 = request.form.get('fio2', type=float)
    peep = request.form.get('peep', type=int)
    pao2 = request.form.get('pao2', type=float)
    pplat = request.form.get('pplat', type=float)
    ph = request.form.get('ph', type=float)
    strategy = request.form.get('strategy')

    current = Vent(vt, rr, fio2, peep)
    ards = ARDSNet(current)
    ards.adjustVent(ph, pao2, pplat, hp=(strategy == 'highpeep'))

    if patient:
        absvt = ards.vent.vt * patient.pbw
    else:
        absvt = 0

    return render_template(
        "main.j2",
        vent=ards.vent,
        vt=ards.vent.vt,
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
