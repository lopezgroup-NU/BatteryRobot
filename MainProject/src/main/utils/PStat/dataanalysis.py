#Functions initially developed by Thanh Nguyn & Willa Brenneis

"""
If bumps is reinstalled, add these lines to the fit function at the end of fitters.py in the bumps source code.
This returns the values you can use in the form of a dict.

obj = {}
obj["final chisq"] = problem.chisq_str()
err = driver.stderr_from_cov()
for k, v, dv in zip(driver.problem.labels(), driver.problem.getp(), err):
    obj[str(k)] = format_uncertainty(v, dv)
return result, obj
"""

import matplotlib.pyplot as plt
from impedance.models.circuits import Randles, CustomCircuit
import numpy as np
from .BUMPS import *
import time
import math

class DataAnalyzer():

    #data = pd.read_excel(r"C:\Users\llf1362\Downloads\postClean3e.xlsx")
    # data = pd.read_csv(r"C:/Users/llf1362/Desktop/BatteryRobot/MainProject/src/main/utils/PStat/galvanostatic_eis.csv", sep = ",")
    # data = pd.read_csv(r"C:/Users/llf1362/Desktop/BatteryRobot/MainProject/src/main/galvanostatic_eis.csv", sep = ",")
    #data = pd.read_csv(r"C:\Users\llf1362\Downloads\Run_50000_2_C03.txt", sep = "\t")
    #data = pd.read_csv(r"C:\Users\llf1362\Downloads\galvanostatic_eis.csv", sep = ",")

    def __init__(self, csv_path):
        self.bump = BUMPS()
        self.data = pd.read_csv(csv_path, sep =",")
        self.ReZ_data_1 = self.data['zreal']
        self.f_data1 = self.data['freq']
        self.ImZ_data_1 = -self.data["zimag"]

        # #Biologic
        # ReZ_data_1 = data['Re(Z)/Ohm']
        # f_data1 = data['freq/Hz']
        # ImZ_data_1 = data[" -Im(Z)/Ohm"]
        self.minR = self.ReZ_data_1[np.argmin(self.ImZ_data_1)]


    def impedance(self, x, R1, R2, R3, alpha1, alpha2,  sigma1, sigma2):
        w = 2*np.pi*x
        Z1 = sigma1*((1j*w)**alpha1)
        Z2 = sigma2*((1j*w)**alpha2)
        RC1 = 1 / (1/(R1) + Z1)
        RC2 = 1 / (1/(R2) + Z2)
        Rf =  R3 + RC1 + RC2
        return Rf

    def impedance1(self, x, R1, R2, alpha1, sigma1):
        w = 2*np.pi*x
        RC2 = 1 /(1/R2 + sigma1*((1j*w)**alpha1))
        Rf = R1 + RC2
        return Rf

    def Zreal(self,  x, R1, R2, R3, alpha1, alpha2,  sigma1, sigma2):
        return self.impedance( x, R1, R2, R3, alpha1, alpha2,  sigma1, sigma2).real

    def Zimag(self,  x, R1, R2, R3, alpha1, alpha2,  sigma1, sigma2):
        return -(self.impedance( x, R1, R2, R3, alpha1, alpha2,  sigma1, sigma2).imag)

    def Zreal1(self, x, R1, R2, alpha1, sigma1):
        return self.impedance1(x,  R1,  R2, alpha1, sigma1).real

    def Zimag1(self, x,  R1,  R2, alpha1, sigma1):
        return -(self.impedance1(x,   R1, R2, alpha1, sigma1).imag)

    def fit_model(self, x, Zr, Zi, fname, steps):
        x = x
        y1 = Zr
        dy1 = np.abs(Zr)
        y2 = np.abs(Zi)
        dy2 = np.abs(Zi)
        
        params1 = [bmp.Parameter(name = "R1", value = self.minR).range(1, np.inf),
                   bmp.Parameter(name = "R2", value = self.minR*1000).range(1, np.inf),
                bmp.Parameter(name = "alpha1", value = .5).range(0, 1),
                bmp.Parameter(name = "sigma1", value = 1e-6).range(0, 1)]
        
        params = [bmp.Parameter(name = "R1", value = self.minR*100).range(0, np.infty),
                bmp.Parameter(name = "R2", value = self.minR*100000).range(0, np.infty),
                bmp.Parameter(name = "R3", value = self.minR).range(1, np.inf),
                bmp.Parameter(name = "alpha1", value = .5).range(0, 1),
                bmp.Parameter(name = "alpha2", value = .5).range(0, 1),
                bmp.Parameter(name = "sigma1", value = 1e-6).range(0, 1),
                bmp.Parameter(name = "sigma2", value = 1e-6).range(0, 1)]

        for i in range(len(Zr)):
            dy1[i] *= 0.05
            dy2[i] *= 0.05 

        self.bump.addfunction(self.Zreal1,params1)
        self.bump.addmodel(x,y1,dy1)
        self.bump.addfunction(self.Zimag1,params1)
        self.bump.addmodel(x,y2,dy2)

        self.bump.setproblem(self.bump.models)
    #     bump.plotfit()
        self.bump.settings['dream']['steps']=steps

        self.bump.fitproblem()
        obj = self.bump.obj
        
    #     bump.plotfit()
        self.bump.savefitresult(fname=fname)
        return self.bump, obj

    def imp(self, fdata, Zrdata, Zimgdata):

        f = fdata
#         f = [val for val in f if val < 99 or val > 500]
        Zp = Zrdata
        Zpp = []
        for i in range(len(Zimgdata)):
            Zpp.append(-Zimgdata[i])
        
        Z = []
        Y = []
        for i in range(len(Zimgdata)):
            Z.append(Zp[i] + 1j*Zpp[i])
            Y.append(1/Z[i])
        
        return np.asarray(f),np.asarray(Z)

    def run(self, fname):
        f_d, Z_d = self.imp(self.f_data1, self.ReZ_data_1, self.ImZ_data_1)
        
        mask = (Z_d.real > 0) & (-Z_d.imag > 20) 
        self.bump, obj = self.fit_model(f_d[mask], Z_d[mask].real, -Z_d[mask].imag,
                                    fname = 'res/bumps/'+ fname + ".xlsx",steps=5000)
        
        return obj
        # 1000 steps ~ 10seconds
        # 5000 ~ 50seconds
        #7000 ~ 70 seconds
        #10000 ~ 100 secs
        #i guess it scales linearly
        # p = bump.getparameters()[0]['par']
        # # 
        # fit_ZR = bump.models[0].fn(f_d[mask],*p)
        # fit_ZI = bump.models[1].fn(f_d[mask],*p)
        # # 
        # fig, ax = plt.subplots(1,1,figsize=(6,6))
        # ax.plot(Z_d.real[mask],-Z_d.imag[mask],marker='o',linestyle='',mec='#005162',mfc='None',markersize=5)  
        # ax.plot(fit_ZR,fit_ZI,marker='',linestyle='-',color='k',linewidth=2)   
        # plt.xlabel("Z Real (Ohm)")
        # plt.ylabel("-Z Imaginary (Ohm)")
        # plt.show()



