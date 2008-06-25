
import random
import copy
import re
from subprocess import Popen, PIPE
from util import gform
import config

class Source:
    def __init__(self, sourcetype='bilateral', sourceparams=None, sourceparams_str=None):
        '''Create parameterized earthquake source.
        
        Creates earthquake source with given parameters. Any parameters not specified,
        are filled with default values.
        
           sourcetype: Type of the source (bilateral, circular, eikonal, ...)
           sourceparams: dict with source parameters defining the source.
           
        The object returned can be used almost like a dict.'''
    
        self._sourcetype = sourcetype
        self._params = {}
        
        if not sourceparams_str is None:
            sourceparams_float = [ float(s) for s in sourceparams_str.split() ]
            for i,sparam in enumerate(param_names(self._sourcetype)):
                self._params[sparam] = sourceparams_float[i]
        
        if sourceparams is None:
            sourceparams = {}
            
        for sparam in param_names(self._sourcetype):
            self._params[sparam] = source_infos(self._sourcetype)[sparam].default
        
        self.update( sourceparams )
    
    def sourcetype(self):
        return self._sourcetype
    
    def sourceinfo(self,param=None):
        if param is None:
            return source_infos(self._sourcetype)
        else:
            return source_infos(self._sourcetype)[param]
    
    def __getitem__(self, param):
        return self._params[param]
    
    def __setitem__(self, param, value):
        if param in param_names(self._sourcetype):
            self._params[param] = float(value)
        else:
            raise Exception('invalid source parameter: "%s" for source type: "%s"'% (param, self._sourcetype) )
            
    def update(self, sourceparams):
        for param in sourceparams.keys():
            self[param] = sourceparams[param]
    
    def keys(self):
        return list(param_names(self._sourcetype))
        
    def values(self):
        return [ self[k] for k in self.keys() ]
    
    def items(self):
        return [ (k, self[k]) for k in self.keys() ]
    
    def __str__(self):
        return self._sourcetype + ' ' + ' '.join( [ str(f) for f in self.values() ] )
    
    def pretty_str(self):
        si = source_infos(self._sourcetype)
        kwid = max( [ len(k) for k in self.keys() ] )
        uwid = max( [ len(si[k].unit) for k in self.keys() ] )
        str_params = '\n'.join( [ '    %s [%s]: %s' % (k.ljust(kwid), si[k].unit.center(uwid), gform(v,3)) for k,v in self.items() ] )
        return 'sourcetype: %s\n' % self._sourcetype + str_params
    
    def update_from_list(self, values):
        for sparam, value in zip( self.keys(), values):
            self[sparam] = float(value)

    def grid( self, grid_definition, source_constraints=None):
        """Create a grid of sources, based on this source.
         
        grid_definition: A list of tuples, each defining parameter name, minimum,
            maximum and stepsize for each grid parameter as follows:
        
                  [(parameter, minimum, maximum, stepsize), ...]
                  
            Example:
        
             grid_definition = [ ('time', -10, 10, 2 ), ('dip', 0, 90, 30) ]
        
        source_constraints: Function callback, which may be used to turn off
            individual points of the grid. The function is called with the current 
            source as argument and must return True or False in order to turn on or 
            turn off the grid node in question.
           """
        return self._make_source_grid( grid_definition, source_constraints=None )
    
    def _make_source_grid( self, sourceparams, irecurs=0, paramlist=None, sourceslist=None, source_constraints=None ):
        
        if paramlist is None:
            paramlist = [0.] * len(sourceparams)
            
        if sourceslist is None:
            sourceslist = []
            
        key = sourceparams[ irecurs ][0]
        vmin, vmax, vstep = [ float(v) for v in sourceparams[ irecurs ][1:] ]
        n = int(round((vmax-vmin)/vstep))+1
        vstep = (vmax-vmin)/(n-1)
        for i in xrange(n):
            v = vmin + i * vstep
            paramlist[irecurs] = v
            if irecurs < len(sourceparams)-1:
                self._make_source_grid( sourceparams, irecurs+1, paramlist, sourceslist, source_constraints=source_constraints )
            else:
                v = {}
                for i,elem in enumerate(sourceparams):
                    v[elem[0]] = paramlist[i]
                
                s = copy.deepcopy(self)
                s.update(v)
                if source_constraints == None or source_constraints(s):
                    sourceslist.append(s)
        
        return sourceslist
        
    def randomize( self, sourceparams, nsources ):
        '''Make random sources based on this one.
               
        sourceparams: A list of tuples, each defining parameter name, minimum,
            and maximum of the parameter range: 
        
                [(parameter, minimum, maximum), ...]
                
        nsources: Number of sources to create.
        '''
        sourceslist = []
        for isource in xrange(nsources):
            v = {}
            for iparam in xrange(len(sourceparams)):
                key = sourceparams[ iparam ][0]
                vmin, vmax = [float(x) for x in sourceparams[ iparam ][1:] ]
                v[key] = random.uniform(vmin, vmax)
            
            s = copy.deepcopy(self)
            s.update(v)
            sourceslist.append(s)
            
        return sourceslist


    

class SourceInfo:
    info = None
    info_flat = None
    
def source_types():
    """Get available source types."""
    
    if SourceInfo.info is None:
        SourceInfo.info, SourceInfo.info_flat = get_source_infos()
     
    return SourceInfo.info.keys()
     

def source_infos( sourcetype ):
        """get some information about possible sources"""
    
        if SourceInfo.info is None:
            SourceInfo.info, SourceInfo.info_flat = get_source_infos()
        
        return SourceInfo.info[sourcetype]

def source_infos_flat( sourcetype ):
        """get some information about possible sources"""
    
        if SourceInfo.info is None:
            SourceInfo.info, SourceInfo.info_flat = get_source_infos()
        
        return SourceInfo.info_flat[sourcetype]

def param_names( sourcetype ):
        """returns param names in correct order for given source type"""
    
        if SourceInfo.info is None:
            SourceInfo.info, SourceInfo.info_flat = get_source_infos()
            
            
        return SourceInfo.info_flat[sourcetype]["name"]
            
def get_source_infos():
        """get some information about possible sources in minimizer by asking source_info"""
        info = {}
        info_flat = {}
        
        class Entry:
            pass
        
        # get avail. source types
        cmd = [ config.source_info_prog ]
        
        source_info = Popen( cmd, stdout=PIPE ).communicate()[0].splitlines()
        
        for line in source_info:
            if re.match(r'\s*source types: ', line):
                sourcetypes = re.sub(r'\s*source types: ','',line).split()
        
        
        # get parameter names for source types
        for sourcetype in sourcetypes:
            cmd = [ config.source_info_prog, sourcetype ]
           
            source_info = Popen( cmd, stdout=PIPE ).communicate()[0].splitlines()
            
            key_translate = { 'parameter names: ': 'name',
                              'parameter units: ': 'unit',
                              'parameter hard min: ': 'hard_min',
                              'parameter hard max: ': 'hard_max',
                              'parameter soft min: ': 'soft_min',
                              'parameter soft max: ': 'soft_max',
                              'parameter defaults: ': 'default' }
                              
            params_flat = {} 
            for line in source_info:
                # string fields
                for key in ['parameter names: ',
                            'parameter units: ']:
                            
                    if re.match(r'\s*'+key, line):
                        pars = re.sub(r'\s*'+key, '', line).split()
                        pkey = key_translate[key]
                        params_flat[pkey] = pars
                        
                for key in ['parameter hard min: ',
                            'parameter hard max: ',
                            'parameter soft min: ',
                            'parameter soft max: ',
                            'parameter defaults: ' ]:
                            
                    if re.match(r'\s*'+key, line):
                        pars = [ float(s) for s in re.sub(r'\s*'+key, '', line).split() ]
                        pkey = key_translate[key]
                        params_flat[pkey] = pars
                        
            info_flat[sourcetype] = params_flat
            
            params = {}
            for i,pname in enumerate(params_flat['name']):
                entry = Entry()
                for key in params_flat.keys():
                    setattr(entry, key, params_flat[key][i])
                params[pname] = entry
                        
            info[sourcetype] = params
            
        return info, info_flat

if __name__ == '__main__':
    s = Source('eikonal')
    for s in s.randomize( [('time',-10,10),('dip',0,90)], 10):
        print s
    print s.pretty_str()
