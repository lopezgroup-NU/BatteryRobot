#PWR800 Pain
import sys
from enum import Enum
import toolkitpy as tkp

#sys.path.append(r'C:\Users\ablack.GAMRY\Documents\Jupyter\Supporting\Release')
#from enumerations import cell_types
#from toolkitcommon import *
import ctypes
#from toolkitcurves import *
#  -------------- PWR Signal Acquisition Defaults ---------------
global PWR800_DEFAULT_PERTURBATION_RATE
global PWR800_DEFAULT_PERTURBATION_WIDTH
global PWR800_DEFAULT_TIMER_RESOLUTION
global PWR800_DEFAULT_MAXIMUM_STEP
global PWR800_DEFAULT_MINUMUM_DIFFERENCE
global PWR800_DEFAULT_CV_CP_GAIN
global PWR800_DEFAULT_CR_GAIN
global PWR800_DEFAULT_TI 
PWR800_DEFAULT_PERTURBATION_RATE = 0.01
PWR800_DEFAULT_PERTURBATION_WIDTH = 0.003333
PWR800_DEFAULT_TIMER_RESOLUTION = 0.0016666666
PWR800_DEFAULT_MAXIMUM_STEP = 0.05
PWR800_DEFAULT_MINUMUM_DIFFERENCE = 0.15
PWR800_DEFAULT_CV_CP_GAIN = 0.05
PWR800_DEFAULT_CR_GAIN = 1.0
PWR800_DEFAULT_TI = 5.0
#----------------- PWR Stop At Delay Globals ------------------
global PWR800_DEFAULT_DTEMP_DELAY
PWR800_DEFAULT_DTEMP_DELAY = 30.0
#-------------------- PWR title string Globals ---------------------
global CCD_TITLE
global CHARGE_TITLE 
global DISCHARGE_TITLE 
global POLARIZATIONCURVE_TITLE
global PWRCV_TITLE
global PWREISGALV_TITLE 
global PWREISGALVSTREAM_TITLE 
global PWREISGALVTHD_TITLE
global PWRGALVANOSTATIC_TITLE
global PWRHYBRIDEIS_TITLE
global PWRLEAKAGECURRENT_TITLE
global PWRPOTENTIOSTATIC_TITLE
global PWRREADVOLTAGE_TITLE
global PWRSELFDISCHARGE_TITLE
global PWREISGALVMON_TITLE
global PWREISHYBMON_TITLE
global PWRDISCHARGEPROFILE_TITLE
CCD_TITLE = "PWR Cyclic Charge Discharge"
CHARGE_TITLE = "PWR Charge"
DISCHARGE_TITLE = "PWR Discharge"
POLARIZATIONCURVE_TITLE = "PWR Polarization"
PWRCV_TITLE = "PWR Cyclic Voltammetry"
PWREISGALV_TITLE = "PWR Galvanostatic EIS"
PWREISGALVSTREAM_TITLE = "PWR Galvanostatic stream EIS"
PWREISGALVTHD_TITLE = "PWR Galvanostatic EIS THD"
PWRGALVANOSTATIC_TITLE = "PWR Galvanostatic"
PWRHYBRIDEIS_TITLE = "PWR Hybrid EIS"
PWRLEAKAGECURRENT_TITLE = "PWR Leakage Current"
PWRPOTENTIOSTATIC_TITLE = "PWR Potentiostatic"
PWRREADVOLTAGE_TITLE = "PWR Read Voltage"
PWRSELFDISCHARGE_TITLE = "PWR Self-Discharge"
PWREISGALVMON_TITLE = "PWR Galvanostatic Single Frequency EIS"
PWREISHYBMON_TITLE = "PWR Hybrid Single Frequency EIS"
PWRDISCHARGEPROFILE_TITLE = "PWR Discharge Profile"

global SIGNAL_CHANGING_THRESHOLD
SIGNAL_CHANGING_THRESHOLD = 0.05

def Capacity(Powerexperiment):
       return None

def PWR800initializepstat(pstat, IRToggle, cell_type, aesbhcselector):
    IruptTime = 20.0E-6
    SAMPLINGMODE_NR = 1
    pstat.set_cell(CELL_OFF)
#Implement cell type check this has to do with if the instrument is a dual electrometer instrument.
    pstat.set_ctrl_mode(GSTATMODE)
    pstat.set_ie_stability(STABILITY_FAST)
    pstat.set_ca_speed(CASPEED_NORM)
    pstat.set_sense_speed(SENSE_SLOW)
    pstat.set_sense_speed_mode(False)
    pstat.set_ground(FLOAT)
    pstat.set_ich_range(3.0)
    pstat.set_ich_range_mode(True)
    pstat.set_ich_offset_enable(False)
    pstat.set_ich_filter(60000.0)
    pstat.set_vch_range(10.0)
    pstat.set_vch_range_mode(True)
    pstat.set_vch_offset_enable(False)
    pstat.set_vch_filter(60000.0)
    pstat.set_ach_range(3.0)
    pstat.set_ach_offset_enable(False)
    pstat.set_ach_range_mode(True)
    pstat.set_ach_filter(60000.0)
    ##Clearing pstat gets rid of this lower limit
    pstat.set_ie_range_lower_limit(7)
    pstat.set_analog_out(0.0)
    pstat.set_pos_feed_enable(False)
    pstat.set_dds_enable(False)
    if (IRToggle):
            # Pstat.set_irupt_mode(IruptOff, EUEXTRAP, IruptTime, POTEN.Eoc(), 1.0) ###I do not know what POTEN.EOC does I assume it probably takes an EOC !!!
            #pstat.set_vch_filter (100000.0)
            print("Implementation needed")
    else:
            pstat.set_irupt_mode(IRUPTOFF)
            return
def PWR800ConfigureAndConfirm(pstat, expected_max_v, working, cell_type, aesbhc_selector,display_config):
       expected_max_v = abs(expected_max_v)
       config_valid = True
       lmodel = pstat.model_no()
       laesbhc_selector = False
       lelectrometer = None
       configure_cell = CELL_TYPE()
       lcompliance_voltage = None
       lach_select = None
       warn = None 
       warn_config = "The selected instrument does not support the requested config."
       warnMaxV = "The expected maximum voltage exceeds the instrument capability."
       warnPosReq = "The selected instrument & config requires positive working connection."
       warnDualMeas = "The selected instrument cannot perform dual electrometer measurements."
       warnSetElect = "The selected instrument and requested config is not valid.  Use alternate electrometer."
       warnCompliance = "The selected instrument compliance voltage must be set to High."
       if (lmodel == MODELNO.IFC5000):#We have to check what the interface actually comes up as !!!
              lach_select = ACHSELECT_CSEL
              if(expected_max_v > 6.0):
                     warn = warnMaxV
                     config_valid = False
              elif (cell_type == cell_types.CELL_TYPE_FULL): #Create enumerations for the cell type
                     if (working):
                            cable_check_positive = "WE, WS"
                            cable_check_negative = "CS, CE"
                     else: 
                            cable_check_positive = "CE, CS"
                            cable_check_negative = "WE, WS"
                     cable_check_reference = None
                     cable_check_ground = "RE"
                     lelectrometer = ELECTROMETER_CS
                     pstat.set_ctrl_mode(ZRAMODE) #Ask Morgan about this !!!
                     laesbhc_selector = False 
              elif ( cell_type == cell_types.CELL_TYPE_HALF):
                     if (working == True):
                            cable_check_positive = "WE, WS"
                            cable_check_negative = "CE"
                     else:
                            cable_check_positive = "CE"
                            cable_check_negative = "WE, WS"
                     cable_check_reference = "RE"
                     cable_check_ground = "CS"
                     lelectrometer = ELECTROMETER_RE
                     pstat.set_ctrl_mode(PSTATMODE)
                     laesbhc_selector = False
              elif (cell_type == cell_types.CELL_TYPE_BOTH):
                     if (working == True):
                            cable_check_positive = "WE, WS"
                            cable_check_negative = "CE, CS"
                     else:
                            cable_check_postiive = "CE, CS"
                            cable_check_negative =  "WE, WS"
                     cable_check_reference = "RE"
                     cable_check_ground = None
                     lelectrometer = ELECTROMETER_CS
                     pstat.set_ctrl_mode(ZRAMODE)
                     laesbhc_selector = True
              else:
                     warn = warnSetElect
                     config_valid = False
              
       elif (lmodel == MODELNO.EBX5000):
              lelectrometer = ELECTROMETER_RE
              pstat.set_ctrl_mode(PSTATMODE)
              if (expected_max_v > 6.0):
                     warn = warnMaxV
                     config_valid = False
              elif (cell_type == cell_types.CELL_TYPE_FULL):
                     if(working == True):
                            cable_check_positive = "WE, WS"
                            cable_check_negative = "CE, RE"
                     elif (working == False):
                            cable_check_positive = "CE, RE"
                            cable_check_negative = "WE, WS"
                     cable_check_reference = None
                     cable_check_ground = None
              elif (cell_type == cell_types.CELL_TYPE_HALF):
                     if(working == True):
                            cable_check_positive = "WE, WS"
                            cable_check_negative = "CE"
                     elif (working == False):
                            cable_check_positive = "CE"
                            cable_check_negative = "WE, WS"
                     cable_check_reference = "RE"
                     cable_check_ground = None
              elif (cell_type == cell_types.CELL_TYPE_BOTH):
                     warn = warnDualMeas
                     config_valid = False
              else: 
                     warn = warn_config
                     config_valid = False
              
       elif (lmodel == MODELNO.EBX1010):
              lelectrometer = ELECTROMETER_RE
              pstat.set_ctrl_mode(PSTATMODE)
              if (expected_max_v > 12.0):
                     warn = warnMaxV
                     config_valid = False
              elif (cell_type == cell_types.CELL_TYPE_FULL):
                     if(working == True):
                            cable_check_positive = "WE, WS"
                            cable_check_negative = "CE, RE"
                     elif (working == False):
                            cable_check_positive = "CE, RE"
                            cable_check_negative = "WE, WS"
                     cable_check_reference = None
                     cable_check_ground = None
              elif (cell_type == cell_types.CELL_TYPE_HALF):
                     if(working == True):
                            cable_check_positive = "WE, WS"
                            cable_check_negative = "CE"
                     elif (working == False):
                            cable_check_positive = "CE"
                            cable_check_negative = "WE, WS"
                     cable_check_reference = "RE"
                     cable_check_ground = None
              elif(cell_type == cell_types.CELL_TYPE_BOTH):
                     warn = warnDualMeas
                     config_valid = False
              else:
                     warn = warn_config
                     config_valid = False
       elif(lmodel == MODELNO.PC61000 or lmodel == MODELNO.PC61010 or lmodel == MODELNO.REF600 or lmodel == MODELNO.REF600P or lmodel== MODELNO.REF620):
              lelectrometer = ELECTROMETER_RE
              if (expected_max_v > 12):
                     warn = warnMaxV
                     config_valid = False
              elif (cell_type == cell_types.CELL_TYPE_FULL):
                     if (working == True):
                            cable_check_positive = "WE, WS"
                            cable_check_negative = "CE, RE"
                     elif (working == False):
                            cable_check_positive = "CE, RE"
                            cable_check_negative = "WE, WS"
                     cable_check_reference = None
                     cable_check_ground = "CS"
              elif (cell_type == cell_types.CELL_TYPE_HALF):
                     if (working == True):
                            cable_check_positive = "WE, WS"
                            cable_check_negative = "CE"
                     elif (working == False):
                            cable_check_positive = "CE"
                            cable_check_negative = "WE, WS"
                     cable_check_reference = "RE"
                     cable_check_ground = "CS"
              elif (cell_type == cell_types.CELL_TYPE_BOTH):
                     warn = warnDualMeas
                     config_valid = False
              else:
                     warn = warn_config
                     config_valid = False
       elif (isinstance(lmodel, (MODELNO.REF3000, MODELNO.REF3020))):
              lach_select = ACHSELECT_CSEL
              lcompliance_voltage = pstat.compliance_voltage()
              if (expected_max_v > 32):
                     warn = warnMaxV
                     config_valid = False
              elif ( expected_max_v > 15 and lcompliance_voltage != COMPLIANCE_HIGH ):
                     warn = warnCompliance
                     config_valid = False
              elif (cell_type == cell_types.CELL_TYPE_FULL and expected_max_v < 12):
                     if (working == True):
                            cable_check_positive = "WE, WS"
                            cable_check_negative = "CE, RE"
                     else:
                            cable_check_positive = "CE, RE"
                            cable_check_negative = "WE, WS"
                     cable_check_reference = None
                     cable_check_ground = "CS"
                     lelectrometer = ELECTROMETER_RE
                     pstat.set_ctrl_mode(PSTATMODE)

              elif (cell_type == cell_types.CELL_TYPE_FULL and expected_max_v > 12):
                     if(working == True):
                            cable_check_positive = "WE, WS"
                            cable_check_positive = "CE, RS"
                            cable_check_reference = None
                            cable_check_ground = "RE"
                            lelectrometer = ELECTROMETER_CS
                            pstat.set_ctrl_mode(ZRAX4MODE)
              else:
                     warn = warnPosReq
                     config_valid = False
       elif(cell_type == cell_types.CELL_TYPE_HALF and expected_max_v < 12):
              if(working == True):
                     cable_check_positive = "WE, WS"
                     cable_check_postiive = "CE"
              else:
                     cable_check_postiive = "CE"
                     cable_check_negative = "WE, WS"
              cable_check_reference = "RE"
              cable_check_ground = "CS"
              lelectrometer = ELECTROMETER_RE
              pstat.set_ctrl_mode(PSTATMODE)
       elif(cell_types.CELL_TYPE_HALF and expected_max_v > 12):
              if(working == True):
                     cable_check_positive  = "WE, WS"
                     cable_check_negative = "CE"
                     cable_check_reference = "CS"
                     cable_check_ground = "RE"
                     lelectrometer = ELECTROMETER_CS
                     pstat.set_ctrl_mode(ZRAX4MODE)
              else: 
                     warn = warnPosReq
                     config_valid = False
       elif(cell_type == cell_types.CELL_TYPE_BOTH): 
              warn = warnDualMeas
              config_valid = False
       else:
              warn - warn_config
              config_valid = False
    

       if (config_valid == False):
              errormessage = warn
              result = ctypes.windll.user32.MessageBoxW(0,errormessage, "Error", 0x30 | 0x0)
              del pstat
              toolkitpy_close()
              sys.exit()
              return
       if (lelectrometer is None):
              result = ctypes.windll.user32.MessageBoxW(0,"Invalid Electrometer Setting", "Error", 0x30 | 0x0)
       if(lelectrometer  is not None):
              configure_cell.set_electrometer(lelectrometer)
       if(lcompliance_voltage is not None):
              configure_cell.set_compliance_voltage(lcompliance_voltage)
       if(lach_select is not None):
              configure_cell.set_ach_select(lach_select)
       if(working is not None):
              configure_cell.set_working(working)
       configure_cell.initialize(pstat)
       #figure out what to do with the aesbhcselector. PRobably take the value out somewhere and then store it so we know if we are using it. 


       confirmation_message = "pstat: {} \n ".format(pstat.label()) 
       confirmation_message = confirmation_message + "Connect : {} to Postive\n ".format(cable_check_positive)
       confirmation_message = confirmation_message + "Connect : {} to Negative\n ".format(cable_check_negative)
       if (cable_check_reference is not None):
              confirmation_message = confirmation_message + "Connect : {} to Reference\n ".format(cable_check_reference)
       if (cable_check_ground is not None):
              confirmation_message = confirmation_message + "Connect : {} to Ground\n ".format(cable_check_ground)
       if(display_config == True): 
              result = ctypes.windll.user32.MessageBoxW(0, confirmation_message, "Configure", 0x0 | 0x0)
       pstat.set_vch_range_mode(True)
       voltage_reading = pstat.measure_v()
       if (working and voltage_reading < -.005) or (working == False and voltage_reading >.005):
              measurement_message = ("Pstat: {}\n ".format(pstat.label()))
              measurement_message = measurement_message + "Voltage is : {} V\n Press YES to allow it or NO to restart".format(voltage_reading)
              result = ctypes.windll.user32.MessageBoxW(0,measurement_message, "Warning", 0x03 | 0x0)
              if (result == 1):
                     sys.exit
       

class CELL_TYPE(): 
    def __init__(self):
           self.electrometer = ELECTROMETER_RE
           self.compliance_voltage = None
           self.ach_select = ACHSELECT_GND
           self.working = None

           
    def initialize(self, pstat): 
           if(pstat.has('ELECTROMETER_CS') and (self.electrometer is not None)):
              pstat.set_electrometer(self.electrometer)
           if(self.compliance_voltage is not None):
                  pstat.set_compliance_voltage(self.compliance_voltage)
           if(self.ach_select is not None):
                  pstat.set_ach_select(self.ach_select)
           if (self.working == True):
                  pstat.set_i_convention(ANODIC)
           elif(self.working == False):
                  pstat.set_i_convention(ANODIC)
           pstat.set_i_convention(ANODIC)
    def set_electrometer(self, electrometer): 
           self.electrometer = electrometer
    def get_electrometer(self):
        return self.electrometer 
    def set_compliance_voltage(self, compliance_voltage):
           self.set_compliance_voltage = compliance_voltage
    def set_ach_select(self, ach_select):
           self.ach_select = ach_select
    def set_working(self, working):
           self.working = working
    
                  
                  
            
     
                     
              
                        

              
              
                     
                     

              