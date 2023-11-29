'''
MIDAS native reader, based on 
https://bitbucket.org/tmidas/midas/src/develop/python/examples/file_reader.py

A. Capra
October 2021
'''

import midas.file_reader as file_reader
import numpy as np
import os, glob
import errno

class MIDASreader:
    '''
    Iterable object to unpack MIDAS events
    Usage:
    mreader=MIDASreader(<list of MIDAS files>, <str indicating the ADC model>, <list of MIDAS data banks>)
    for i,event in enumerate(mreader):
        print(f'Event # {i}\t#Modules {event.nboards}\t#Channels {event.nchannels}\t#Samples {event.nsamples}')
         print(f'\tchannel mask {bin(event.channel_mask)[2:]}\ttrigger time: {event.trigger_time}')
        # access waveforms in event
        event.adc_data # shape = (number of channels, number of waveform sample)

    '''
    def __init__(self, manager):
        self.m  = manager
        try:
            if os.path.isdir(self.m.config.input):
                print(f'{self.m.config.input} is a directory')
                # get list of midas files, exclude odb dumps (*.json)
                # compressed (*.mid.lz4, *.mid.gz) or uncompressed
                self.midas_files  = glob.glob(f'{self.m.config.input}/*mid*')
                # ensure subruns are processed in chrnonological order
                self.midas_files.sort()
        except TypeError:
            # copy the list of files
            self.midas_files  = self.m.config.input

        self.subidx=0
        self.__next_subrun__()
        
        MIDASconf={"proto0":{"ADC":'V1725',"BANKS":["W200","W201","W202","W203"],'bin':4},
                   "dart":{"ADC":'V1730',"BANKS":["WF00"],'bin':4},
                   "NAsetup1":{"ADC":'V1725',"BANKS":["W200","W201","W202","W203"],'bin':4},
                   "NAsetup2":{"ADC":'VX2740',"BANKS":["D000","D001"],'bin':8},
                  }
        data_format =  self.m.config('daq', 'data_format', 'str') # files_list
        self.ADCmodel = MIDASconf[data_format]['ADC']             # adc_model
        self.ADCbanks = MIDASconf[data_format]['BANKS']           # banks_list
        self.event_number=0

    def isADCbank(self,current_bank):
        '''
        ensure that the data from ADCs and not from other equipment
        '''
        if current_bank in self.ADCbanks: return True
        else: return False

    def __next__(self):
        ev = self.read()
        if not ev:
            raise StopIteration()
        else:
            return ev

    def __iter__(self):
        return self

    def __next_subrun__(self):
        if self.subidx < len(self.midas_files):
            fname=self.midas_files[self.subidx]
            if os.path.isfile(fname):
                self.mfile = file_reader.MidasFile(fname,use_numpy=True)
                print(f'subrun {self.subidx}: {fname}')
                self.subidx+=1
            else:
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), fname)

    def read(self):
        '''
         main function to unpack ADC data
         returns waveform array (number of channels, number of samples)
        '''
        for event in self.mfile:
            if event.header.is_midas_internal_event():
                if event.header.is_eor_event():
                    self.__next_subrun__()
                    return self.read()
                continue

            if self.ADCmodel == 'V1725':
                raw = unpack_V1725()
            elif self.ADCmodel == 'V1730':
                raw = unpack_V1730()
            elif self.ADCmodel == 'VX2740':
                raw = unpack_VX2740()
            else:
                raise ValueError(f'Unknown ADC model {self.ADCmodel}\nAvailable models V1725, V1730, VX2740')

            for bank_name, bank in event.banks.items():
                if len(bank.data) and self.isADCbank(bank_name):
                    raw.unpack(bank.data)

            raw.midas_event=event.header.serial_number
            return raw
                    

class unpack_ADC:
    '''
    Base class to unpack ADC data
    '''
    def __init__(self,model):
        self.name=model
        self.adc_data=np.array([])
        self.nboards=0
        self.nchannels=0
        self.nsamples=0
        self.midas_event=-1
        self.event_counter=np.uint64(0)
        self.trigger_time=np.uint64(0) # ns
        self.channel_mask=0

    def info(self):
        print(f'''ADC: {self.name}   #Modules: {self.nboards:3d}   #Channels: {self.nchannels:4d}
MIDAS S/N: {self.midas_event:6d}   Trigger Counter: {self.event_counter:6d}   Trigger Timestamp: {self.trigger_time:6d} ns''')

class unpack_V1725(unpack_ADC):
    def __init__(self):
        super().__init__('V1725')
            
    def unpack(self,bank_data):
        self.unpackHeader(bank_data[:4])
        if not self.zlecompressed:
            self.unpackData(bank_data[4:])
            self.nchannels=self.adc_data.shape[0]
            self.nsamples=self.adc_data.shape[1]
        else:
            print('V1725 ZLE is not currently supported')
        
    def unpackHeader(self,head_data):
        self.header=np.array(head_data,dtype='uint32')
        self.event_size=self.header[0] & 0xffffff
        self.channel_mask=(self.header[1] & 0xff) + ((self.header[2] & 0xff000000) >> 16)
        self.zlecompressed=(self.header[1] >> 26) & 0x1
        self.event_counter=np.uint64(self.header[2] & 0xffffff)
        self.trigger_tag=np.uint64(self.header[3] & 0xffffffff)
        self.extended_trigger_tag=np.uint64((self.header[1] >> 8 ) & 0xffff)
        self.trigger_time=((self.extended_trigger_tag<<np.uint64(32))+self.trigger_tag)*np.uint64(8)
    
    def unpackData(self,bank_data):
        data = np.array(bank_data,dtype='uint32')
        self.nboards+=1
        slot1 = np.uint16( data&0x3FFF )      # first 16 bits correspond to 'even samples'
        slot2 = np.uint16( (data>>16)&0x3FFF )# second 16 bits correspond to 'odd samples'
        nchans = bin(self.channel_mask).count('1')
        n32samples = np.uint32( (self.event_size - 4) / nchans )
        # order samples properly and group by channel
        waveforms = np.ravel([slot1,slot2],'F').reshape(nchans,2*n32samples)
        self.adc_data=np.vstack([self.adc_data,waveforms]) if self.adc_data.size else waveforms


class unpack_V1730(unpack_ADC):
    def __init__(self):
        super().__init__('V1730')
            
    def unpack(self,bank_data):
        self.unpackHeader(bank_data[:8])
        self.unpackData(bank_data[8:])
        self.nchannels=self.adc_data.shape[0]
        self.nsamples=self.adc_data.shape[1]
        
    def unpackHeader(self,head_data):
        self.header=np.array(head_data,dtype='uint16')
        self.channel_mask = self.header[0]
        self.flags = self.header[1]
        self.samples = (np.uint32(self.header[3])<<np.uint32(16))+np.uint32(self.header[2])
        self.event_counter+=np.uint64(1)
        self.trigger_time = (np.uint64(self.header[7])<<np.uint64(48))+(np.uint64(self.header[6])<<np.uint64(32))+(np.uint64(self.header[5])<<np.uint64(16))+np.uint64(self.header[4])

    def unpackData(self,bank_data):
        data=np.array(bank_data,dtype='uint16')
        self.nboards+=1
        nchans = bin(self.channel_mask).count('1')
        waveforms = data.reshape(nchans,self.samples)
        self.adc_data=np.vstack([self.adc_data,waveforms]) if self.adc_data.size else waveforms


class unpack_VX2740(unpack_ADC):
    def __init__(self):
        super().__init__('VX2740')
            
    def unpack(self,bank_data):
        self.unpackHeader(bank_data[:3])
        if self.format == 0x10:
            self.unpackData(bank_data[3:])
            self.nchannels=self.adc_data.shape[0]
            self.nsamples=self.adc_data.shape[1]
        else:
            print(self.name,'no scope data')
        
    def unpackHeader(self,head_data):
        self.header=np.array(head_data,dtype='uint64')
        self.format = self.header[0] >> np.uint64(56)
        self.event_counter = (self.header[0] >> np.uint64(32)) & np.uint64(0xffffff)
        self.event_size = self.header[0] & np.uint64(0xffffffff)
        self.flags = self.header[1] >> np.uint64(52)
        self.overlap = (self.header[1] >> np.uint64(48)) & np.uint64(0xf)
        self.channel_mask = self.header[2]
        self.trigger_time = (self.header[1] & np.uint64(0xffffffffffff))*np.uint64(8)
       
    def unpackData(self,bank_data):
        '''
        data format:
        64bit word channel 0 (4 samples), 64bit word channel 1 (4 samples), 
        ... 64bit word channel N (4 samples)
        '''
        data = np.array(bank_data,dtype='uint64')
        self.nboards+=1

        nchans = bin(self.channel_mask).count('1')
        # only 1/4 of the samples
        nsamples = np.uint32((self.event_size - 3) / nchans)
 
        bitmask=np.uint64(0xffff)
        slot1 = (data&bitmask).reshape(nchans,nsamples,order='F')
        slot2 = ((data>>16)&bitmask).reshape(nchans,nsamples,order='F')
        slot3 = ((data>>32)&bitmask).reshape(nchans,nsamples,order='F')
        slot4 = ((data>>48)&bitmask).reshape(nchans,nsamples,order='F')
        waveforms = np.vstack((slot1,slot2,slot3,slot4)).reshape(nchans,nsamples*4,order='F')
        self.adc_data=np.vstack([self.adc_data,waveforms]) if self.adc_data.size else waveforms

