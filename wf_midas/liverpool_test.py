#!/usr/bin/env python3

import matplotlib
#matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from midas_liverpool import MIDASreader
from config import Config
import time
import numpy as np

import matplotlib.patches as mpatches
import os, sys
import pandas as pd
#import msgpack

# sys.path.append('/opt/exp_software/darkside/software/python_local_libraries/')
# sys.path.append('/cvmfs/sft.cern.ch/lcg/views/LCG_96python3/x86_64-centos7-gcc8-opt/lib/python3.6/site-packages/')
# sys.path.append('/cvmfs/sft.cern.ch/lcg/views/LCG_96python3/x86_64-centos7-gcc8-opt/lib')

class AnaNA:
  def __init__(self,**configargs):
    self.config         = Config(**configargs)

    # getting info from .ini files
    self.sampling         = self.config('daq', 'sampling', 'float') # S/s
    self.timebin          = 1e9/self.sampling # ns
    self.baseline_to      = self.config('reco', 'bl_to', 'int')
    self.n_trig_events    = self.config('roi', 'n_trigs', 'int')
    # number of samples to the left of the trigger position
    self.roi_left_samples = self.config('roi', 'roi_low', 'int')
    # total number of samples in the ROI
    self.roi_tot_samples  = self.config('roi', 'roi_tot', 'int')
    # settings 
    self.channel_to_plot = -1


  def plot_wf(self,wfs):
    x = np.linspace(0,len(wfs[0])/125,len(wfs[0]))
    # Create a 2x2 grid of subplots
    fig, axs = plt.subplots(2, 2, figsize=(12, 8))
    # Plot data on each subplot
    axs[0, 0].plot(x,wfs[0],linewidth=0.5,color='k')
    axs[0, 0].set_title('Ch 0')
    axs[0, 0].set_xlabel('Time (us)')
    axs[0, 0].set_ylabel('Voltage (ADC)')

    axs[0, 1].plot(x,wfs[1],linewidth=0.5,color='k')
    axs[0, 1].set_title('Ch 1')
    axs[0, 1].set_xlabel('Time (us)')
    axs[0, 1].set_ylabel('Voltage (ADC)')


    axs[1, 0].plot(x,wfs[2],linewidth=0.5,color='k')
    axs[1, 0].set_title('Ch 2')
    axs[1, 0].set_xlabel('Time (us)')
    axs[1, 0].set_ylabel('Voltage (ADC)')

    axs[1, 1].plot(x,wfs[3],linewidth=0.5,color='k')
    axs[1, 1].set_title('Ch 3')
    axs[1, 1].set_xlabel('Time (us)')
    axs[1, 1].set_ylabel('Voltage (ADC)')

    plt.tight_layout()
    plt.show()
    plt.close()

    # Create a 2x2 grid of subplots
    fig1, axs1 = plt.subplots(2, 2, figsize=(12, 8))

    # Plot data on each subplot
    axs1[0, 0].plot(x,wfs[4],linewidth=0.5,color='k')
    axs1[0, 0].set_title('Ch 4')
    axs1[0, 0].set_xlabel('Time (us)')
    axs1[0, 0].set_ylabel('Voltage (ADC)')

    axs1[0, 1].plot(x,wfs[5],linewidth=0.5,color='k')
    axs1[0, 1].set_title('Ch 5')
    axs1[0, 1].set_xlabel('Time (us)')
    axs1[0, 1].set_ylabel('Voltage (ADC)')

    axs1[1, 0].plot(x,wfs[6],linewidth=0.5,color='k')
    axs1[1, 0].set_title('Ch 6')
    axs1[1, 0].set_xlabel('Time (us)')
    axs1[1, 0].set_ylabel('Voltage (ADC)')

    axs1[1, 1].plot(x,wfs[7],linewidth=0.5,color='k')
    axs1[1, 1].set_title('Ch 7')
    axs1[1, 1].set_xlabel('Time (us)')
    axs1[1, 1].set_ylabel('Voltage (ADC)')

    plt.tight_layout()
    plt.show()
    plt.close()


  def reco(self):
     
     #Definiting time taken to read data 
     t0 = time.time()
     t1 = t0

     self.events   = MIDASreader(manager=self)

     
     empty_event = 0 
     
     #Loop to extract information from each events in all channels
     for nev, event in enumerate(self.events):
        #Summing the number of empty events
        if event is None:
          empty_event += 1
          continue

        if event.nchannels == 0: 
          empty_event += 1
          continue

        if nev%1000 == 0 and nev>0: # progress print
          print(f'{nev:6d} events {time.time()-t1:1.3f}s / 1000 ev')
          t1 = time.time()

        wfs = 1 * (event.adc_data) 
        #self.plot_wf(wfs)




        
        
     

if __name__ == '__main__':

  r = AnaNA()
  r.reco()