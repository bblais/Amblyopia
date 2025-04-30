import numpy as np
import pylab as py
import asdf
import warnings
warnings.filterwarnings("ignore",category=asdf.exceptions.AsdfDeprecationWarning)

second=1
ms=0.001*second
minute=60*second
hour=60*minute
day=24*hour

class Struct(dict):

    def __getattr__(self,name):

        try:
            val=self[name]
        except KeyError:
            val=super(Struct,self).__getattribute__(name)

        return val

    def __setattr__(self,name,val):

        self[name]=val


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

def reformat_time_axis():
    import matplotlib
    
    def HMSFormatter(value, loc): 
        h = value // 3600 
        m = (value - h * 3600) // 60 
        s = value % 60 

        d=h//24
        h=h%24
        if d==0:
            return "%02d:%02d:%02d" % (h,m,s) 
        else:
            return "%dd %02d:%02d:%02d" % (d,h,m,s) 

    def HMSFormatter2(value, loc): 
        h = value // 3600 
        m = (value - h * 3600) // 60 
        s = value % 60 
        ms=value%1

        return "%02d:%02d.%03d" % (m,s,ms*1000) 


    ax=py.gca()
    xl=ax.get_xlim()

    if xl[1]<10:  # use ms
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(HMSFormatter2)) 
    else:
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(HMSFormatter)) 

    py.gcf().autofmt_xdate()

def plotvar(t,y,name,*args,**kwargs):
    import matplotlib.pyplot as plt 
    import matplotlib.ticker 

    def HMSFormatter(value, loc): 
        h = value // 3600 
        m = (value - h * 3600) // 60 
        s = value % 60 

        d=h//24
        h=h%24
        if d==0:
            return "%02d:%02d:%02d" % (h,m,s) 
        else:
            return "%dd %02d:%02d:%02d" % (d,h,m,s) 

    def HMSFormatter2(value, loc): 
        h = value // 3600 
        m = (value - h * 3600) // 60 
        s = value % 60 
        ms=value%1

        return "%02d:%02d.%03d" % (m,s,ms*1000) 

    if np.max(t)<10:  # use ms
        py.gca().xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(HMSFormatter2)) 
    else:
        py.gca().xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(HMSFormatter)) 

    py.plot(t,y,*args,**kwargs) 
    py.gcf().autofmt_xdate()

    py.ylabel(name)



def plot_mini_rfs(fname,*args):
    
    with asdf.open(fname) as af:
        L=af.tree['attrs']['sequence length']

        vmin=1e500
        vmax=-1e500
        i=0
        while i<len(args):
            _t,_x,_y=args[i:i+3]
            i+=3

            for si in range(L):
                m=af.tree['sequence %d' % si]['connection 0']['monitor weights']
                t,W=m['t'],m['values']

                idx=np.where(t>=_t)[0][0]

                if idx:
                    ww=W[idx,:]
                    break
            
            if min(ww)<vmin:
                vmin=W.min()
            if max(ww)>vmin:
                vmax=W.max()

    

        if 'channel' in af.tree['sequence 0']['neuron 0']['attrs']['type']:
             number_of_channels=af.tree['sequence 0']['neuron 0']['attrs']['number_of_neurons']
        else:
            number_of_channels=1
            
        N=len(np.array(af.tree['sequence 0']['neuron 0']['output']))
        
        rf_size=int(np.sqrt(N/number_of_channels))
        
        i=0
        while i<len(args):
            _t,_x,_y=args[i:i+3]
            i+=3

            for si in range(L):
                m=af.tree['sequence %d' % si]['connection 0']['monitor weights']
                t,W=m['t'],m['values']

                idx=np.where(t>=_t)[0][0]

                if idx:
                    ww=W[idx,:]
                    break

            for c in range(number_of_channels):
                ax2 = py.gcf().add_axes([_x+.06*c, _y, 0.05, 0.1],aspect='equal')
                subw=ww[c*rf_size*rf_size:(c+1)*rf_size*rf_size]
                w_rf=subw.reshape((rf_size,rf_size))

                h=ax2.pcolormesh(w_rf,cmap=py.cm.gray,
                        vmin=vmin,vmax=vmax)
                ax2.set_xticklabels([])
                ax2.set_yticklabels([])
                ax2.xaxis.set_ticks_position('none') 
                ax2.yaxis.set_ticks_position('none') 

def plot_max_response(fname,which_neurons=None):
    
    with asdf.open(fname) as af:
        L=af.tree['attrs']['sequence length']
    
        for i in range(L):
            m=af.tree['sequence %d' % i]['simulation']['process 0']
            t,responses=m['t'],m['responses']


            num_channels,num_neurons=responses.shape[2],responses.shape[3]

            if which_neurons is None:
                which_neurons=range(num_neurons)
                Ln=num_neurons
            else:
                Ln=len(which_neurons)

            for si,ni in enumerate(which_neurons):
                subplot(Ln,1,si+1)
                for ch in range(num_channels):
                    y=responses[:,:,ch,ni,:].max(axis=0).max(axis=0)
                    plotvar(t,y,'max response',
                            marker='.', linestyle='-')

def plot_max_spatial_frequency(fname,which_neurons=None):
    
    with asdf.open(fname) as af:
        L=af.tree['attrs']['sequence length']
    
        for i in range(L):
            m=af.tree['sequence %d' % i]['simulation']['process 0']
            t,responses,theta,k=m['t'],m['responses'],m['theta_mat'],m['k_mat']

            num_channels,num_neurons=responses.shape[2],responses.shape[3]

            if which_neurons is None:
                which_neurons=range(num_neurons)
                Ln=num_neurons
            else:
                Ln=len(which_neurons)

            for si,ni in enumerate(which_neurons):
                subplot(Ln,1,si+1)
                for ch in range(num_channels):
                    y=k[responses[:,:,ch,ni,:].max(axis=1).argmax(axis=0)]
                    plotvar(t,y,'max $k$',
                            marker='.', linestyle='-')
                
                
                
def plot_theta(fname):
    with asdf.open(fname) as af:
        L=af.tree['attrs']['sequence length']
        
        for i in range(L):
            m=af.tree['sequence %d' % i]['connection 0']['monitor theta']           
            t,theta=m['t'],m['values']
            plotvar(t,theta,'theta')