import toolkitpy as tkp
import os 
from datetime import datetime 
from datetime import date
class Experiment():
    def __init__(self, stop_ats):
        self.stop_ats = stop_ats
    
    def hold_stop_ats(self,stop_ats):
        self.stop_ats = stop_ats
    
    def filter_stop_ats(self, curve,pstat_mode):
        """Make sure that the stop ats input are compatible with the curve
        
        Parameters
        -----------
        curve : tkp.toolkitcurves
            The input curve to apply the stop ats
        pstat_mode : tkp.PSTATMODE
            The pstat mode this determines if the stop ats are voltage or current based
        
        **kwargs: 
            The actual stop ats to apply
        """
        new_dict = {}
        if isinstance(curve, tkp.toolkitcurves.ChronoACurve):
            if pstat_mode == tkp.PSTATMODE:
                if 'vmin' in self.stop_ats:
                    new_dict["xmin"] = self.stop_ats.pop("imin")
                if 'vmax' in self.stop_ats:
                    new_dict["xmax"] = self.stop_ats.pop("imax")
            elif pstat_mode == tkp.GSTATMODE:
                if 'vmin' in self.stop_ats:
                    new_dict["xmin"] = self.stop_ats.pop("vmin")
                if 'vmax' in self.stop_ats:
                    new_dict["xmax"] = self.stop_ats.pop("vmax")
        elif isinstance(curve, tkp.toolkitcurves.RcvCurve):
            if pstat_mode == tkp.PSTATMODE:
                if 'imin' in self.stop_ats:
                    new_dict["imin"] = self.stop_ats.pop("imin")
                if 'imax' in self.stop_ats:
                    new_dict["imax"] = self.stop_ats.pop("imax")
        elif isinstance(curve, tkp.toolkitcurves.OcvCurve):
            if "stability" in self.stop_ats:
                new_dict["stability"] = self.stop_ats.pop("stability")
        if self.stop_ats: #Test if the dicionary is empty
            curve_name = str(type(curve))
            curve_name = curve_name[curve_name.rfind('.')+1:]
            tkp.log.warning(f"Filtered kwargs: {self.stop_ats}, these stop ats are not compatible with the {curve_name}")
        self.stop_ats = new_dict
    def ready_echem_analyst_file(self):
        self.file_name = os.path.splitext(self.file_name)[0]
        self.file_name = self.file_name + ".DTA"
        current_date = date.today().strftime("%d/%m/%Y")
        with open(self.file_name, "w") as file:
            print("EXPLAIN", file = file)
        return file
   
    def print_hardware_settings(self,pstat,file):
            print(f"PSTATSECTION\tLABEL\t{pstat.section()}\tPstat Section", file = file)
            print(f"PSTATSERIALNO\tLABEL\t{pstat.serial_no()}\t Pstat Serial Number", file = file)
            print(f"CTRLMODE\tIQUANT\t{int(pstat.ctrl_mode())}\tControl Mode", file = file)
            print(f"IESTAB\tIQUANT\t{int(pstat.ie_stability())}\tI/E Stability", file = file)
            print(f"CASPEED\tIQUANT\t{int(pstat.ca_speed())}\tControl Amp Speed", file = file)
            print(f"CONVENTION\tIQUANT\t{int(pstat.i_convention())}\tCurrent Convention", file = file)
            print(f"ICHRANGE\tIQUANT\t{pstat.ich_range()}\tIch Range", file = file)
            if pstat.ich_range() == True:
                string = "T"
            else:
                string = "F"
            print(f"ICHRANGEMODE\tTOGGLE\t{string}\t Ich Auto Range", file = file)
            if pstat.ich_offset_enable():
                string = "T"
            else:
                string = "F"
            print(f"ICHOFFSETENABLE\tTOGGLE\t{string}\tIch offset Enable", file = file)
            print(f"ICHOFFSET\tQUANT\t{pstat.ich_offset()}\tIch Offset (V)", file = file)
            print(f"ICHFILTER\tIQUANT\t{pstat.ich_filter()}\t Ich Filter", file = file)
            print(f"VCHRANGE\tIQUANT\t{pstat.vch_range()}\tVch Range", file = file)
            if pstat.vch_range_mode():
                string = "T"
            else:
                string = "F"
            print(f"VCHRANGEMODE\tTOGGLE\t{string}\tVch Auto Range", file = file)
            if pstat.vch_offset_enable():
                string = "T"
            else:
                string = "F"
            print(f"VCHOFFSETENABLE\tTOGGLE\t{string}\tVch Offset Enable", file = file)
            print(f"VCHOFFSET\tQUANT\t{pstat.vch_offset()}\tVch Offset (V)", file = file)
            print(f"VCHFILTER\tIQUANT\t{pstat.vch_filter()}\tVch Filter", file = file)
            print(f"ACHRANGE\tIQUANT\t{int(pstat.ach_range())}\tAch Range", file = file)
            if pstat.ach_offset_enable():
                string = "T"
            else:
                string = "F"
            print(f"ACHOFFSETENABLE\tTOGGLE\t{string}\tAch Offset Enable", file = file)
            print(f"ACHOFFSET\tQUANT\t{pstat.ach_offset()}\tAch Offset (V)", file = file)
            print(f"ACHFILTER\tIQUANT\t{pstat.ach_filter()}\tAch Filter", file = file)
            print(f"IERANGELOWERLIMIT\tIQUANT\t{pstat.ie_range_lower_limit()}\tI/E Range Lower Limit", file = file)
            if pstat.ie_range_mode():
                string = "T"
            else:
                string = "F"
            print(f"IERANGEMODE\tTOGGLE\t{string}\tI/E AutoRange", file = file)
            print(f"IERange\tIQUANT\t{pstat.ie_range()}\tI/E Range", file = file)
            if pstat.pos_feed_enable():
                string = "T"
            else:
                string = "F"
            print(f"POSFEEDENABLE\tTOGGLE\t{string}\tPositive Feedback IR COMP", file = file)
            print(f"POSFEEDRESISTANCE\tQUANT\t{pstat.pos_feed_resistance()}\tPositive Feedback Resistance (ohm)", file = file)
            print(f"ACHSELECT\tIQUANT\t{int(pstat.ach_select())}\tAch Select", file = file)
            print(f"SenseCABLEID\tIQUANT\t{pstat.cable_id(tkp.CID_MAIN)}\tSense Cable ID", file = file)
            print(f"PWRCABLEID\tIQUANT\t{pstat.cable_id(tkp.CID_PWR)}\tPower Cable ID", file = file)
            print(f"DCCALDATE\tLABEL\t{pstat.cal_date(0)}\tDC Calibration Date", file = file)
            print(f"ACCALDATE\tLABEL\t{pstat.cal_date(1)}\tAC Calibration Date", file = file)
            print(f"THERMOSELECT\tIQUANT\t{int(pstat.thermo_select())}\tThermo Select", file = file)
            print(f"INSTRUMENTVERSION\tLABEL\t{pstat.insturment_version(tkp.SUBSYSTEM_CPU)}\tInstrument Version", file = file)
            print(f"COMMVERSION\tLABEL\t{pstat.insturment_version(tkp.SUBSYSTEM_COMM)}\tCommunications Version", file = file)
            print(f"CPUPLDVERSION\tLABEL\t{pstat.insturment_version(tkp.SUBSYSTEM_CPU)}\tCPU PLD Version", file = file)
            print(f"CTRLPLDVERSION\tLABEL\t{pstat.insturment_version(tkp.SUBSYSTEM_CONTROL)}\tCTRL PLD Version", file = file)
            print(f"PSTATPLDVERSION\tLABEL\t{pstat.insturment_version(tkp.SUBSYSTEM_PSTAT)}\tPSTAT PLD Version", file = file)
            print(f"COMPLIANCEVOLTAGE\tIQUANT\t{int(pstat.compliance_voltage())}\tCompliance Voltage",file = file)
            
    def set_stop_ats(self, curve):
        if not self.stop_ats:
             tkp.log.info("No stop ats specified")
        else:
            if "vmin" in self.stop_ats:
                curve.set_stop_v_min(True, self.stop_ats["vmin"])
            if "vmax" in self.stop_ats:
                curve.set_stop_v_max(True, self.stop_ats["vmax"])
            if "imin" in self.stop_ats:
                curve.set_stop_i_min(True, self.stop_ats["imin"])
            if "imax" in self.stop_ats:
                curve.set_stop_i_max(True, self.stop_ats["imax"])
            if "xmax" in self.stop_ats:
                curve.set_stop_x_max(True, self.stop_ats["xmax"])
            if "xmin" in self.stop_ats:
                curve.set_stop_x_min(True, self.stop_ats["xmin"])
            if "stability" in self.stop_ats:
                curve.set_stop_adv_min(True, self.stop_ats["stability"])
            tkp.log.info("Stop at setting successfully set")


    def get_last_value(self):
            """This function returns the last voltage or current depending on if the experiment was run using galvanostatic or potentiostatic mode"""
            if self.last_value is None:
                 tkp.log.warning("You haven't run an experiment yet to get the last value of!")
            else:
                 return self.last_value
