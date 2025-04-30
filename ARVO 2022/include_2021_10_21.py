import plasticnet as pn
from splikes.utils import paramtext
import process_images_hdf5 as pi5
import os
from savevars import loadvars,savevars

from numpy import linspace,sqrt,array
import numpy as np

from science import *

def get_responses(fname):
    import asdf
    data=[]
    with asdf.open(fname) as af:
        L=af.tree['attrs']['sequence length']
    
        for i in range(L):
            m=af.tree['sequence %d' % i]['simulation']['process 0']
            t,responses=m['t'],m['responses']
            data.append( (array(t),array(responses)) )
        
        k_mat=array(m['k_mat'])
        theta_mat=array(m['theta_mat'])
            
    return data,k_mat,theta_mat

import os
import shutil

def sci_format_func(value, tick_number):
    if value==0:
        return "0"
    
    s='%.2g' % value
    
    base=s.split('e')[0]
    exponent=s.split('e')[1]
    
    exponent=exponent.replace('-0','-')
    if exponent[0]=='0':
        exponent=exponent[1:]
        
    return "${0}\cdot 10^{{{1}}}$".format(base,exponent)

def subplot(*args):  # avoids deprication error
    import pylab as plt
    try:
        fig=plt.gcf()
        if args in fig._stored_axes:
            plt.sca(fig._stored_axes[args])
        else:
            plt.subplot(*args)
            fig._stored_axes[args]=plt.gca()
    except AttributeError:
            plt.subplot(*args)
            fig._stored_axes={}
            fig._stored_axes[args]=plt.gca()

    return plt.gca()

from plotutils import *

def within(val,thresh):
    if abs(val)<thresh:
        return True
    else:
        return False
    
    