#Functions initially developed by Thanh Nguyn & Willa Brenneis

import matplotlib.pyplot as plt
from impedance.models.circuits import Randles, CustomCircuit
import numpy as np
from BUMPS import *
import time
import math

#data = pd.read_excel(r"C:\Users\llf1362\Desktop\test2.xlsx")
#data = pd.read_csv(r"C:/Users/llf1362/Desktop/BatteryRobot/MainProject/src/main/utils/PStat/tests/kcl1413mgeis_highF4.csv", sep = ",")
data = pd.read_csv(r"C:\Users\llf1362\Downloads\Run_1413_1_C03.txt", sep = "\t")


#ReZ_data_1 = data[' Zreal (ohm)']
#f_data1 = data['# Freq(Hz)']
#ImZ_data_1 = data[" Zimag (ohm)"]


#Biologic
ReZ_data_1 = data['Re(Z)/Ohm']
f_data1 = data['freq/Hz']
ImZ_data_1 = data["-Im(Z)/Ohm"]
minR = ReZ_data_1[np.argmin(ImZ_data_1)]


def impedance(x, R1, R2, alpha1, alpha2,  sigma1, sigma2):
    w = 2*np.pi*x
    Z1 = sigma1*((1j*w)**alpha1)
    Z2 = sigma2*((1j*w)**alpha2)
    RC1 = 1 / (1/(R1) + 1/Z1)
    RC2 = 1 / (1/(R2) + 1/Z2)
    Rf =  RC1 + RC2
    return Rf

def impedance1(x, C1, R1, R2, sigma):
    w = 2*np.pi*x
    Zw = sigma*w**(-0.5) - 1j*(sigma*w**(-0.5))
    RC2 = 1 / (1/(R2+Zw) + 1j*w*C1)
    Rf = R1 + RC2
    return Rf

def Zreal(x, R1, R2,  alpha1, alpha2, sigma1, sigma2):
    return impedance(x, R1, R2, alpha1, alpha2, sigma1, sigma2).real

def Zimag(x,  R1, R2, alpha1, alpha2, sigma1, sigma2):
    return -impedance(x,  R1, R2,alpha1, alpha2, sigma1, sigma2).imag

def Zreal1(x,C1,R1,R2, sigma):
    return impedance(x, C1, R1, R2,sigma).real

def Zimag1(x, C1, R1, R2,sigma):
    return -impedance(x, C1, R1, R2, sigma).imag

def fit_model(x, Zr, Zi, fname, steps):
    x = x
    y1 = Zr
    dy1 = np.abs(Zr)
    y2 = np.abs(Zi)
    dy2 = np.abs(Zi)
    
    params1 = [bmp.Parameter(name = "C1", value = 1e-12).range(0, 1),
              bmp.Parameter(name = "R1", value = 37000).range(0,np.infty),
              bmp.Parameter(name = "R2", value = 100).range(0, np.infty),
              bmp.Parameter(name = "sigma", value = 1000).range(0, np.infty)]
    
    
    params = [bmp.Parameter(name = "R1", value = minR).range(0, np.infty),
              bmp.Parameter(name = "R2", value = minR*1000).range(0, np.infty),
              bmp.Parameter(name = "alpha1", value = -1).range(-1, 0),
              bmp.Parameter(name = "alpha2", value = -1).range(-1, 0),
              bmp.Parameter(name = "sigma1", value = 1e10).range(0, np.infty),
              bmp.Parameter(name = "sigma2", value = 1e10).range(0, np.infty)]

    for i in range(len(Zr)):
        dy1[i] *= 0.05
        dy2[i] *= 0.05
    
    bump.addfunction(Zreal,params)
    bump.addmodel(x,y1,dy1)
    bump.addfunction(Zimag,params)
    bump.addmodel(x,y2,dy2)

    bump.setproblem(bump.models)
    bump.plotfit()
    bump.settings['dream']['steps']=steps
    bump.fitproblem()
    
    bump.plotfit()
    bump.savefitresult(fname=fname)
    return bump

def imp(fdata, Zrdata, Zimgdata):

    f = fdata
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


start = time.time()

f_d, Z_d = imp(f_data1, ReZ_data_1, ImZ_data_1)

mask = (Z_d.real > 0)  & (-Z_d.imag > 0)  & (f_d < f_d[np.argmin(-Z_d.imag)]*100) & (f_d > f_d[np.argmin(-Z_d.imag)]/100) 
bump = BUMPS()
bump = fit_model(f_d[mask], Z_d[mask].real, -Z_d[mask].imag,
                             fname = 'james.xlsx',steps=50000)

p = bump.getparameters()[0]['par']

fit_ZR = bump.models[0].fn(f_d[mask],*p)
fit_ZI = bump.models[1].fn(f_d[mask],*p)

fig, ax = plt.subplots(1,1,figsize=(6,6))
ax.plot(Z_d.real[mask],-Z_d.imag[mask],marker='o',linestyle='',mec='#005162',mfc='None',markersize=5)  
ax.plot(fit_ZR,fit_ZI,marker='',linestyle='-',color='k',linewidth=2)   
ax.plot(fit_ZR,fit_ZI,marker='',linestyle='-',color='k',linewidth=2)   
plt.xlabel("Z Real (Ohm)")
plt.ylabel("-Z Imaginary (Ohm)")
plt.show()

