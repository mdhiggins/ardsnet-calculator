import enum
import logging
from datetime import datetime


class Gender(enum.Enum):
    Male = "male"
    Female = "female"


class Unit(enum.Enum):
    Centimeter = "cm"
    Inch = "in"


class Patient():
    __PBW_BASE_VALUE = {
        Gender.Male: 50.0,
        Gender.Female: 45.5,
    }

    def __init__(self, gender, height, unit=Unit.Inch):
        self.gender = gender
        if unit == Unit.Centimeter:
            height = height / 0.3937008
        self.height = height

    @property
    def pbw(self):
        return self.__PBW_BASE_VALUE.get(self.gender) + (2.3 * (self.height - 60))


class Vent():
    def __init__(self, vt, rr, fio2, peep):
        self.vt = vt
        self.rr = rr
        if fio2 > 1:
            fio2 = fio2 / 100
        self.fio2 = fio2
        self.peep = peep

    def minuteVentilation(self, patient):
        return self.vt * patient.pbw * self.rr

    def getVtByWeight(self, patient):
        return self.vt / patient.pbw

    def setVtByWeight(self, vt, patient):
        self.vt = vt * patient.pbw

    def __str__(self):
        return "%dml/kg %d %0.0f%% +%d" % (self.vt, self.rr, self.fio2 * 100, self.peep)

    @property
    def fio2String(self):
        return "%0.0f%%" % (self.fio2 * 100)


class ARDSNet():
    __PPLAT_MAX__ = 30
    __PPLAT_MIN__ = 25

    __RR_MAX__ = 35

    __PH_GOAL_MAX__ = 7.45
    __PH_GOAL_MIN__ = 7.30
    __PH_MIN__ = 7.15

    __VT_MIN__ = 4
    __VT_MAX__ = 8

    __PAO2_MIN__ = 55
    __PAO2_MAX__ = 80

    __LOWER_PEEP_HIGHER_FIO2__ = [
        (0.3, 5),
        (0.4, 5),
        (0.4, 8),
        (0.5, 8),
        (0.5, 10),
        (0.6, 10),
        (0.7, 10),
        (0.7, 12),
        (0.7, 14),
        (0.8, 14),
        (0.9, 14),
        (0.9, 16),
        (0.9, 18),
        (1.0, 18),
        (1.0, 20),
        (1.0, 22),
        (1.0, 24)
    ]
    __HIGHER_PEEP_LOWER_FIO2__ = [
        (0.3, 5),
        (0.3, 8),
        (0.3, 10),
        (0.3, 12),
        (0.3, 14),
        (0.4, 14),
        (0.4, 16),
        (0.5, 16),
        (0.5, 18),
        (0.5, 20),
        (0.6, 20),
        (0.7, 20),
        (0.8, 20),
        (0.8, 22),
        (0.9, 22),
        (1.0, 22),
        (1.0, 24)
    ]

    def __init__(self, vent, patient=None):
        self.patient = patient
        self.venthistory = {}
        self.updateVentSettings(vent)

    def updateVentSettings(self, vent):
        self.vent = vent
        self.venthistory[datetime.now] = vent

    '''
    @property
    def vent(self):
        return next([k for k in self.venthistory.keys()])
    '''

    def adjustVent(self, ph=None, pao2=None, pplat=None, hp=False):
        new = Vent(self.vent.vt, self.vent.rr, self.vent.fio2, self.vent.peep)
        if pao2:
            lphf, hplf = self.adjustByPaO2(pao2, self.vent.fio2, self.vent.peep)
            new.fio2, new.peep = hplf if hp else lphf
        if pplat:
            new.vt = self.adjustByPplat(pplat, self.vent.vt)
        if ph:
            new.vt, new.rr = self.adjustBypH(ph, new.vt, self.vent.rr)
        if new != self.vent:
            self.updateVentSettings(new)
        return new

    def adjustByPplat(self, pplat, vt):
        if pplat > self.__PPLAT_MAX__:
            vt = vt - 1
        elif pplat < self.__PPLAT_MIN__ and vt < 6:
            vt = vt + 1
        return vt

    def adjustBypH(self, pH, vt, rr):
        if pH < self.__PH_MIN__:
            if self.vent.rr < self.__RR_MAX__:
                rr = self.__RR_MAX__
            else:
                rr = self.__RR_MAX__
                vt = vt + 1
        elif pH < self.__PH_GOAL_MIN__ and rr < self.__RR_MAX__:
            rr = rr + 2
            if rr > self.__RR_MAX__:
                rr = self.__RR_MAX__
        elif pH > self.__PH_GOAL_MAX__:
            rr = rr - 2
        return vt, rr

    def adjustByPaO2(self, pao2, fio2, peep):
        lphf = (fio2, peep)
        hplf = (fio2, peep)
        if pao2 < self.__PAO2_MIN__:
            ll = [x for x in self.__LOWER_PEEP_HIGHER_FIO2__ if (x[0] >= fio2 and x[1] > peep) or (x[0] > fio2 and x[1] >= peep)]
            lh = [x for x in self.__HIGHER_PEEP_LOWER_FIO2__ if (x[0] >= fio2 and x[1] > peep) or (x[0] > fio2 and x[1] >= peep)]
            if len(ll) > 0:
                lphf = ll[0]
            if len(lh) > 0:
                hplf = lh[0]
        elif pao2 > self.__PAO2_MAX__:
            hl = [x for x in self.__LOWER_PEEP_HIGHER_FIO2__[::-1] if (x[0] <= fio2 and x[1] < peep) or (x[0] < fio2 and x[1] <= peep)]
            hh = [x for x in self.__HIGHER_PEEP_LOWER_FIO2__[::-1] if (x[0] <= fio2 and x[1] < peep) or (x[0] < fio2 and x[1] <= peep)]
            logging.error(hl)
            logging.error(hh)
            if len(hl) > 0:
                lphf = hl[0]
            if len(hh) > 0:
                hplf = hh[0]
        return lphf, hplf
