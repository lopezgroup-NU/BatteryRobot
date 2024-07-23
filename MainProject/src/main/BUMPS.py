# -*- coding: utf-8 -*-
"""
Created on Thu May 27 10:26:32 2021

@author: jjr1573
"""
import bumps.names as bmp
from bumps.fitters import fit
from bumps.formatnum import format_uncertainty
import numpy as np
import inspect
import matplotlib.pyplot as plt
import dill
import pandas as pd

class BUMPS():
    
    def __init__(self):
        try:
            import bumps
        except  ValueError:
            print('You must download bumps to continue')
        
        self.models=list()
        self.functions=list()
        self.parameters=list()
        self.settings={'dream': {'samples':2500,'burn':1000,'population':10,'thinning':1}}
        
    def addfunction(self,function,pars):
        
        ##this automatically scrapes your fit functions into the function list
        
        self.functions.append(function)
#                print(type(locals()[item]))
        print('function added')
        
        self.parameters.append(pars)
        print('parameters added')
        
        
    def addmodel(self,x,y,dy,index=-1):
        
        try:
            function=self.functions[index]##takes the last index - assumes by default that you added the parameters
            parameters=self.parameters[index]
        except ValueError:
            print('Function or Parameter list are empty')
            
        details=inspect.signature(function)
#        print(details)
        self.models.append(bmp.Curve(function,x,y,dy))
        
        ##iterate through parameters
        for key in details.parameters:
            p=getattr(self.models[index],key)
            
            for par in parameters:
                if(par.name==key):
#                    print(key)
                    setattr(self.models[index],key,par)
    
    def setproblem(self,models):
        self.problem = bmp.FitProblem(models)
        
    def fitproblem(self,method='dream'):
        d=self.settings[method]
        
        self.result = fit(self.problem,
                          method='dream', 
                          burn=d['burn'], 
                          pop=d['population'], 
                          init='eps', 
                          thin=d['thinning'], 
                          steps=d['steps'], 
                          store='test',
                          verbose=True)
    
    def plotfit(self,style='log-log'):
        
        plt.figure(figsize=(3,3),dpi=300)
        
        colors=['r','b','g','c','k']
        for i,model in enumerate(self.models):
            x=model.x
            y=model.y
            dy=model.dy
            
            f=model.fn##function
            p=[]
            
            for par in self.parameters[i]:
                p.append(par.value)
#                print(getattr(par,'name.value'))
            
                
#            print(p)
            plt.errorbar(x,y,yerr=dy,linestyle='',marker='o',label='data_%d'%(i+1),markersize=1,c=colors[i])
            plt.plot(x,f(x,*p),linestyle='-',c=colors[i])
            
        plt.xlabel('x')
        plt.ylabel('y')
        
        if('log' in style):
            plt.xscale('log')
            plt.yscale('log')
            
        plt.legend()
        plt.show()
    
    def getparameters(self):
        
        d={}
        
        
        for i,model in enumerate(self.models):
            
            problem=self.problem
            result=self.result
            d[i]={}
            d[i]['label']=[]
            d[i]['par']=[]
            d[i]['par_err']=[]
            
            for key in problem.model_parameters()['models'][i].keys():
                count=0
                for j,l in enumerate(problem.labels()):
                    if l==key:
                        d[i]['label'].append(key)
                        d[i]['par'].append(result.x[j])
                        d[i]['par_err'].append(result.dx[j])
                        count+=1
                    
            if(count!=1):
                d[i]['label'].append(key)
                d[i]['par'].append(problem.model_parameters()['models'][i][key].value)
                d[i]['par_err'].append(0)
        
    
        return d
    
    def savefitresult(self,fname='save.xlsx'):
        d={}
        pars=self.getparameters()
        ##write fit result summary to excel file with filename
        for i,model in enumerate(self.models):
            
            p=[]
            for par in self.parameters[i]:
                p.append(par.value)
           
            f=model.fn##function
            
            d['model_%d'%(i)]={}
            d['model_%d'%(i)]['x']=model.x
            d['model_%d'%(i)]['y']=model.y
            d['model_%d'%(i)]['y_fit']=f(model.x,*p)
            d['model_%d'%(i)]['dy']=model.dy
            
            d['model_%d'%(i)]['par_labels']=pars[i]['label']
            d['model_%d'%(i)]['par_vals']=pars[i]['par']
            d['model_%d'%(i)]['par_err']=pars[i]['par_err']
            
            # Create a Pandas Excel writer using XlsxWriter as the engine.
            writer = pd.ExcelWriter(fname, engine='xlsxwriter')
            
            # Write each dataframe to a different worksheet.
            for key in d.keys():
                df = pd.DataFrame.from_dict(d[key], orient='index').T
                df.to_excel(writer, sheet_name=key)
            
            writer.close()
#            df.to_excel(fname)
        return d 
        
    def save(self):
        return dill.dumps(self)
    
    def load(self,obj):
        self.__dict__.update(dill.loads(obj).__dict__)
        
def unittest():      
    ##set your functions here
    def line(x, m, b):
        return m*x + b
    
    x = [1, 2, 3, 4, 5, 6]##these are the xpoints of the fit data set
    y = [2.1, 4.0, 6.3, 8.03, 9.6, 11.9] #these are the y points of the fit data set
    dy = [0.05, 0.05, 0.2, 0.05, 0.2, 0.2]#these are the dy points of the fit data set
    
    pars=[bmp.Parameter(name='m',value=1).range(0, np.infty),
          bmp.Parameter(name='b',value=10).range(0, np.infty)]#,
    #      bmp.Parameter(name='m',value=1).range(0, np.infty),
    #      bmp.Parameter(name='m',value=1).range(0, np.infty)],
      
    
    f=BUMPS()##instantiates 
    f.addfunction(line,pars)
    f.addmodel(x,y,dy)
    f.setproblem(f.models)
    f.fitproblem()
    
    pars=f.getparameters()
    
    for key in pars.keys():
        print(pars[key].keys())
    
        print(pars[key]['label'],pars[key]['par'],pars[key]['par_err'])
#    f.fitproblem()
    f.savefitresult()
    f.plotfit()

if __name__ == "__main__":
    # execute only if run as a script
    unittest()
#    pass
    