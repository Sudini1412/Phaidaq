#!/usr/bin/env python3

#########################################
#   by Davide Franco (dfranco@in2p3.fr)
#########################################

# Collection of reconstruction algorithms, accepting as
# inputs either 1d (single waveforms) or 2d (set of waveforms).
# For the latter, the matrix is defined as (channel, sample)

import numpy as np
from scipy.ndimage.filters import uniform_filter1d

class Algos:
  def __init__(self):
    print('Reconstruction Algorithms: Activated')

  # compute the rolling median over wfs of an event
  def running_mean(self, wfs, gate=100):
    if wfs.ndim > 1: return uniform_filter1d(wfs, size=gate, axis=1)
    return  uniform_filter1d(wfs, size=gate)

  # substract mean baseline inside the daq
  def get_baseline(self, wfs, gate=500, start=0):
    if wfs.ndim > 1: return np.mean(wfs[:,start:start+gate], axis=1).reshape((-1, 1))
    return np.mean(wfs[start:start+gate])

  # return baseline subtracted waveforms
  def get_subtracted_waveform(self, wfs, gate=500, start=0):
    return self.get_baseline(wfs=wfs,gate=gate, start=0) - wfs

  # return rms
  def get_rms(self, wfs, gate=500):
    if wfs.ndim > 1: return np.std(wfs[:,0:gate], axis=1).reshape((-1, 1))
    return np.std(wfs[0:gate])

  # downsample wfs
  def downsample_wf(self, wfs, rebin):
    if wfs.ndim > 1: return wfs[:,::int(rebin)]
    return wfs[::int(rebin)]

  # rois with from_ and to_ in samples
  def get_roi(self, wfs, gate=500, start=0):
    if wfs.ndim > 1: return np.sum(wfs[:,int(start):int(start+gate)], axis=1).reshape((-1, 1))
    return wfs[:,int(start):int(start+gate)]


  # Return an array of [chennal, start, stop]
  # Parameters:
  #    wfs is a set of waveforms with 0 or 1 values only
  #    min_samples_to_merge is the min number of samples to merge nearby segments of 1
  #
  # This method identifies the starts and stops of contiguous sequence of 1's (segments)
  # Merge those closer than 'min_samples_to_merge'
  # return a list of segments, each with 3 pars: channel, start, stop
  def get_segments(self, wfs, min_samples_to_merge=20):


    # if single channel WF with size N, encapsulate WF in a (1, N) matrix
    # otherwise return (nchs, N) matrix
    if wfs.ndim == 1:
      nchs = 1
      samples = len(wfs)
      wfs    = np.reshape(wfs, (nchs, samples))
    else:
      nchs, samples = np.shape(wfs)

    # create an array of zeros with the same shape of original WFS
    zeros    = np.zeros(nchs)


    # sum two wfs arrays, the first (second) with a 0xnchs at the beginning (end) of the array
    # the sum of the two produces elements = 1 when a step starts or ends
    step     = np.c_[ wfs, zeros] + np.c_[zeros ,  wfs]


    segs = []
    for ch,s in enumerate(step):
      #Return start time and time for the segment
      seg = np.reshape(np.where(s==1),(-1,2))

      if len(seg) ==0: continue
          #segs.append(seg)
          #continue

      #add a fake segment at the beginning
      seg = np.r_[[[-1,-10000]], seg]


      # - flatten the array of segments so that to create a 1d array
      #    of [start, stop, start, ... , stop, start, stop]
      # - remove first start and last stop
      # - reshape into a 2d array so that [[stop, start] .... [stop, start]]
      #   where for each pair stop is referred to the previous segment
      flat_seg   = seg.flatten()[1:-1].reshape(-1,2)
      # calculate the distance between two segments
      # and stick a flat =1 to segments too close to the previous one
      distance  = np.where(flat_seg[:,1]-flat_seg[:,0]<min_samples_to_merge , 1, 0)

      # flat the seg array and remove the first element (first 'fake' start)
      seg       = seg[1:,:].flatten()

      # take the list of starts to be removed
      starts    = distance*2*np.arange(len(distance))
      # take the list of stops to be removed
      stops     = distance*2*(np.arange(len(distance)))-1

      # remove all of starts and stops except the first element
      remove    = np.concatenate((starts,stops))
      remove    = remove[remove!=0]
      not_in_indices = [x for x in range(len(seg)) if x not in remove]

      # reshape the array in order to have a list of [start, stop]
      seg       = np.reshape(seg[not_in_indices],(-1,2))
      nseg     = len(seg)
      if nseg == 0: continue

      # add channel number
      seg = np.c_[np.ones(nseg)*ch, seg]
      segs.append(seg)

    # concatenate and reshape all segments
    if len(segs) == 0: return np.array([None])

    segs = np.concatenate(segs).ravel()
    return segs.reshape(-1,3).astype(int)
