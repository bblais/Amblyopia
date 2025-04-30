import numpy as np

def Expand(s):
    import asdf
    if isinstance(s,dict):
        ns=dict(s)
        for key in ns:
            ns[key]=Expand(ns[key])
        return ns
    elif isinstance(s,list):
        ns=[Expand(_) for _ in s]
        return ns
    elif isinstance(s,asdf.tags.core.ndarray.NDArrayType):
        return np.array(s)
    else:
        return s

def savevars(*args,**kwargs):

    filename=args[0]
    names=args[1:]

    import inspect

    f=inspect.currentframe()
    out=inspect.getouterframes(f)

    local_dict=None
    which_k=None
    for k,oo in enumerate(out):
        dd=oo[0].f_locals
        if all([arg in dd for arg in names]+list(kwargs.keys())):
            local_dict=dd
            which_k=k
    
    if which_k is None:
        raise ValueError("Cannot find at least one of the variables: %s" % str(list(names)+list(kwargs.keys())))

    import datetime
    import os

    timestamp=datetime.datetime.now()

    dirname,fname=os.path.split(filename)
    if dirname and not os.path.exists(dirname):
        print("Making folder %s..." % dirname,end="")
        os.makedirs(dirname)
        print("done.")
        
    import asdf
    import warnings
    warnings.filterwarnings("ignore",category=asdf.exceptions.AsdfDeprecationWarning)

    import sys
    if '.asdf' not in fname:
        raise ValueError('Only implemented saving asdf files.')

    print("Saving %s..." % filename,end='')
    sys.stdout.flush()

    _variable_names=list(args[1:])

    wanted_keys = args[1:]
    L=local_dict
    mydata=dict((k, Expand(L[k])) for k in wanted_keys if k in L)

    for key in kwargs:
        mydata[key]=Expand(kwargs[key])
        _variable_names.append(key)

    mydata['_variable_names']=_variable_names

    ff = asdf.AsdfFile(mydata)
    ff.write_to(filename, all_array_compression='zlib')    
    print("done.")

def loadvars(filename,*args,verbose=False):
    import inspect
    import asdf

    import warnings
    warnings.filterwarnings("ignore",category=asdf.exceptions.AsdfDeprecationWarning)

    if '.asdf' not in filename:
        raise ValueError('Only implemented saving asdf files.')

    return_vars={}
    with asdf.open(filename) as af:
        _variable_names=af.tree['_variable_names']
        print("Found %s" % _variable_names)
        if not args:
            for _var in _variable_names:
                return_vars[_var]=Expand(af[_var])
            
        else:
            for _var in args:
                return_vars[_var]=Expand(af[_var])

    f=inspect.currentframe()
    out=inspect.getouterframes(f)

    local_vars=None
    for i,oo in enumerate(out):
        dd=oo[0].f_locals
        if '__name__' in dd and dd['__name__']=='__main__':
            local_vars=dd
            break
    if local_vars is None:
        raise ValueError("No localspace found")

    if verbose:
        print("Loading...",return_vars.keys())
    local_vars.update(return_vars)

