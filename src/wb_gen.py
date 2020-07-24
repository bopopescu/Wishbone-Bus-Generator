#! /usr/bin/env python 
'''
Created on 2011-02-27

@author: MegabytePhreak
'''

import demjson
import argparse
import os.path
import sys
from math import ceil, log

def log2(x):
    return log(float(x),2)
def clog2(x):
    return int(ceil(log2(x)))

def is_mapping_type(obj, require_set=True):
    """
    Returns ``True`` if an object appears to
    support the ``MappingType`` protocol.

    If ``require_set`` is ``True`` then the
    object must support ``__setitem__`` as
    well as ``__getitem__`` and ``keys``.
    """
    if require_set and not hasattr(obj, '__setitem__'):
        return False
    if hasattr(obj, 'keys') and hasattr(obj, '__getitem__'):
        return True
    else:
        return False

def is_sequence_type(obj, require_set=True):
    """
    Returns ``True`` if an object appears to
    support the ``SequenceType`` protocol.

    If ``require_set`` is ``True`` then the
    object must support ``__setitem__`` as
    well as ``__getitem__``.

    The object must not have a ``keys``
    method.
    """
    if require_set and not hasattr(obj, '__setitem__'):
        return False
    if (not hasattr(obj, 'keys')) and hasattr(obj, '__getitem__'):
        return True
    else:
        return False

    
class wb_settings(object):
    def __init__(self, data_width, address_width):
        self.data_width = data_width
        self.address_width = address_width
        
class wb_main(object):
    def __init__(self, name, address_width, include_address_valid = False):
        self.name = name
        self.address_width = address_width
        self.include_address_valid = include_address_valid
    def __str__(self):
        return self.name
        
class wb_subordinate(object):
    def __init__(self, name, base, size):
        self.name = name
        self.base = base
        self.size = size
        self.address_width = clog2(size)
    def __str__(self):
        return self.name

class wb_bus(object):
    def __init__(self,name, settings = None,mains = [], subordinates = []):
        self.name = name
        self.settings = settings
        self.mains = mains
        self.subordinates = subordinates
    def __str__(self):
        return self.name
           
def is_string(s):
    return isinstance(s,str) or isinstance(s,unicode)

TYPE_INT    = ('Integer',int,None)
TYPE_BOOL   = ('Boolean',bool,None)
TYPE_STRING = ('String',None,is_string)
TYPE_LIST   = ('List',None,is_sequence_type)
TYPE_MAP    = ('Dictionary',None,is_mapping_type)   
   
class wb_builder(object):      
        
    def error(self,string):
        print("Error: %s"%string)
        sys.exit(1)
    
    def infile_error(self, string):
        self.error("%s: %s"%(self.infile.name,string))
        
        
    def verify_type(self, item, type, name = None):
        if type != None:
            if (type[1] != None and not isinstance(item,type[1])) \
                or (type[2] != None and not type[2](item)):
                if name != None:
                    self.infile_error("Field %s must be a %s"%
                           (name,type[0]))
                else:
                    self.infile_error("%s must be a %s"%
                           (item ,type[0]))
                    
    def verify_field(self, within, name, type, default = None):
        if not name in within and default == None:
            self.infile_error("Could not find field '%s' in :\n%s"%
                              (name,within))
        if not name in within:
            within[name] = default
        self.verify_type(within[name],type,name)
        
    def add_line(self, line):
        self.lines.append(self.ts * '  ' + line)  
            
        
    def load_settings(self, settings):
        if not is_mapping_type(settings, require_set=True):
            self.infile_error("The 'settings' section  invalid")
        if not 'data_width' in settings:
            self.infile_error(
                "The 'settings' section does not contain a 'data_width' field")
        if not isinstance(settings['data_width'],int):
            self.infile_error("'data_width' must be an integer")
        self.config.settings = wb_settings(settings['data_width'],
                                             -1)
    
    def load_main(self, main):  
        self.verify_field(main, 'name', TYPE_STRING)
        self.verify_field(main, 'address_width', TYPE_INT)
        self.verify_field(main, 'include_address_valid',TYPE_BOOL, False)
        self.config.mains.append(wb_main(main['name'],
                                             main['address_width'],
                                             main['include_address_valid'] ))
          
    def load_mains(self, mains):
        if len(mains) < 1:
            self.infile_error("At least one main must be defined")
        if len(mains) > 1:
            self.infile_error("Only one main is currently supported")
            
        count = 0;
        addr_width = -1    
        for main in mains:
            self.verify_type(main,TYPE_MAP,"Main %d"%count)
            self.load_main(main)
            count += 1
            
        for main in self.config.mains:
            if main.address_width != addr_width and addr_width != -1:
                self.infile_error("All main address bus widths must match")
            addr_width = main.address_width
            
        self.config.settings.address_width = addr_width

    def load_subordinate(self, subordinate):
        KW_AUTO = 'auto'
        self.verify_field(subordinate, 'name', TYPE_STRING)
        self.verify_field(subordinate, 'base', ("Integer or 'auto'",None,
                                          lambda x: isinstance(x,int) or x == KW_AUTO))
        if(subordinate['base'] ==KW_AUTO):
            max = 0
            for s in self.config.subordinates:
                next = s.base + s.size
                if(next > max):
                    max = next
            subordinate['base'] = max;
            
        self.verify_field(subordinate, 'size', TYPE_INT)   
        size = subordinate['size']
        base = subordinate['base']
            
        if (size & (size-1)) != 0:
            self.infile_error("Subordinate %s's size is not a power of 2"%subordinate['name'])
        if (base & ~(size-1)) != base: 
            self.infile_error("Subordinate %s is not size-aligned"%subordinate['name'])
            
        self.config.subordinates.append( wb_subordinate(
                    subordinate['name'], base, size))
        
    def load_subordinates(self, subordinates):      
        if len(subordinates) < 1:
            self.infile_error("At least one subordinate must be defined")
     
        count = 0;
        for subordinate in subordinates:
            self.verify_type(subordinate, TYPE_MAP, "Subordinate %d"%count)
            self.load_subordinate(subordinate)
            count += 1
        for subordinatea in self.config.subordinates:
            for subordinateb in self.config.subordinates:
                if not (subordinatea.base < subordinateb.base or \
                    subordinatea.base >= subordinateb.base + subordinateb.size) \
                    and subordinatea != subordinateb:
                    self.infile_error("Subordinates '%s' and '%s' overlap"%
                                      (subordinatea,subordinateb))
                    
    def load_config(self,jsonconfig):
        self.verify_type(jsonconfig, TYPE_MAP, "The config root")
        
        self.verify_field(jsonconfig, "name", TYPE_STRING)
        
        self.config = wb_bus(str(jsonconfig['name']))
        
        for sect in(('settings',TYPE_MAP,self.load_settings),
                       ('mains',TYPE_LIST,self.load_mains),
                       ('subordinates',TYPE_LIST, self.load_subordinates)):
            self.verify_field(jsonconfig,sect[0],sect[1] )
            sect[2](jsonconfig[sect[0]])

       
    
    def print_header(self):
        self.add_line('// *** THIS FILE IS GENERATED BY wb_gen.py ')
        self.add_line('// *** DO NOT MODIFY THIS FILE ')
        self.add_line('// *** GENERATED FROM:')
        self.add_line('// *** %s'%self.infile.name)
        self.add_line('// %d main, %d subordinate %s wishbone interconnect'%
                            (len(self.config.mains),len(self.config.subordinates),
                             "shared bus"))
        self.add_line('//')
        self.add_line('// ADDRESS MAP')
        for subordinate in self.config.subordinates:
            self.add_line("// %8s: 0x%X - 0x%X"%
                          (subordinate.name,subordinate.base,subordinate.base + subordinate.size - 1))
            
    def add_main_port(self, main):
        self.add_line("//Main port '%s':"%main.name)
        self.add_line('input wire [%d:0] %s_adr_i,'%
                      (main.address_width-1,main.name))
        self.add_line('output reg [%d:0] %s_dat_o,'%
                      (self.config.settings.data_width-1,main.name))
        self.add_line('input wire  [%d:0] %s_dat_i,'%
                      (self.config.settings.data_width-1,main.name))
        self.add_line('input wire        %s_cyc_i,'%
                      (main.name))
        self.add_line('input wire        %s_stb_i,'%
                      (main.name))
        self.add_line('input wire        %s_we_i,'%
                      (main.name))
        self.add_line('output reg       %s_ack_o,'%
                      (main.name))
        if(main.include_address_valid):
            self.add_line('output wire       %s_adrv_o,'%(main.name))
            
    def add_subordinate_port(self, subordinate):
        self.add_line("//Subordinate port '%s':"%subordinate.name)
        self.add_line('output wire [%d:0] %s_adr_o,'%
                      (subordinate.address_width-1,subordinate.name))
        self.add_line('output wire [%d:0] %s_dat_o,'%
                      (self.config.settings.data_width-1,subordinate.name))
        self.add_line('input wire  [%d:0] %s_dat_i,'%
                      (self.config.settings.data_width-1,subordinate.name))
        self.add_line('output wire       %s_cyc_o,'%
                      (subordinate.name))
        self.add_line('output wire       %s_stb_o,'%
                      (subordinate.name))
        self.add_line('output wire       %s_we_o,'%
                      (subordinate.name))
        self.add_line('input wire        %s_ack_i,'%
                      (subordinate.name))
    def add_wire_throughs(self):
        main = self.config.mains[0]
        for subordinate in self.config.subordinates:
            self.add_line('assign %s_adr_o = %s_adr_i[%s:0];'%
                          (subordinate.name,main.name,subordinate.address_width-1))
            self.add_line('assign %s_we_o = %s_we_i;'%
                          (subordinate.name,main.name))
            self.add_line('assign %s_dat_o = %s_dat_i;'%
                          (subordinate.name,main.name))
    
    def add_addr_decode(self):
        main = self.config.mains[0]
        ssel_width = clog2(len(self.config.subordinates)+1)
        self.add_line('reg [%d:0] s_sel;'%(ssel_width - 1))
        self.add_line('always @*')
        self.ts += 1
        count = 1;
        for subordinate in self.config.subordinates:
            self.add_line("if( %s_adr_i[%d:%d] == %d'd%d)"%
                (main.name,main.address_width-1,subordinate.address_width, 
                 main.address_width - subordinate.address_width, 
                 subordinate.base >> (subordinate.address_width )))
            self.ts += 1
            self.add_line("s_sel = %d'd%d;"%(ssel_width,count))
            self.ts -= 1
            self.add_line("else")
            count +=1
        self.ts += 1
        self.add_line("s_sel = %d'd0;"%(ssel_width))
        self.ts -= 1 
        self.ts -= 1
        
    def add_m2s_muxes(self):
        main = self.config.mains[0]
        ssel_width = clog2(len(self.config.subordinates)+1)
        count = 1
        for subordinate in self.config.subordinates:
            self.add_line("assign %s_stb_o = (s_sel==%d'd%d)? %s_stb_i : 1'b0;"%
                          (subordinate.name,ssel_width,count,main.name))
            self.add_line("assign %s_cyc_o = (s_sel==%d'd%d)? %s_cyc_i : 1'b0;"%
                          (subordinate.name,ssel_width,count,main.name))
            count +=1 
            
    def add_s2m_muxes(self):
        main = self.config.mains[0]
        ssel_width = clog2(len(self.config.subordinates)+1)
        count = 1
        self.add_line("always @*")
        self.ts += 1
        self.add_line("case(s_sel) /* synthesis parallel_case */")
        self.ts += 1
        for subordinate in self.config.subordinates:
            self.add_line("%d'd%d: begin"%(ssel_width,count))
            self.ts += 1 
            self.add_line("%s_dat_o = %s_dat_i;"%(main.name, subordinate.name))
            self.add_line("%s_ack_o = %s_ack_i;"%(main.name, subordinate.name))
            self.ts -= 1
            self.add_line("end")
            count += 1
       
        self.add_line("default: begin")
        self.ts += 1 
        self.add_line("%s_dat_o = 0;"%(main.name))
        self.add_line("%s_ack_o = 0;"%(main.name))
        self.ts -= 1
        self.add_line("end")
        self.ts -= 1
        self.add_line("endcase")
        self.ts -= 1
        self.add_line("assign %s_adrv_o = s_sel != 0;"%main.name)
        
            
            
    def build_module_decl(self):
        self.add_line('module %s('%self.config.name)
        self.ts += 5
        for main in self.config.mains:
            self.add_main_port(main)
        for subordinate in self.config.subordinates:
            self.add_subordinate_port(subordinate)
        self.add_line('//Syscon connections')
        self.add_line('input wire clk_i,')
        self.add_line('input wire rst_i')
        self.add_line(');')
        self.ts -=4
  
        
    def build_interconnect(self):
        self.build_module_decl()
        self.add_wire_throughs()  
        self.add_line('')  
        self.add_addr_decode()
        self.add_line('')
        self.add_m2s_muxes()
        self.add_line('')
        self.add_s2m_muxes()
        self.ts -=1
        self.add_line('endmodule')
    
    def __init__(self):
        argparser = argparse.ArgumentParser(
                            description='Build a Wishbone bus interconnect')
        argparser.add_argument('inpath', help='Bus description file name')
        argparser.add_argument('-o', dest = 'outpath', help='Output file name')
        args = argparser.parse_args()
        
        if args.outpath == None:
            args.outpath = os.path.splitext(args.inpath)[0] +".v" 
        self.infile = open(args.inpath)
        jsonconfig = demjson.decode(self.infile.read(), strict=True,
                                     allow_comments=True, 
                                     allow_hex_numbers=True,
                                     allow_nonstring_keys=True, 
                                     allow_trailing_comma_in_literal=True)
        self.infile.close();
        self.load_config( jsonconfig )   
        self.ts = 0
        self.lines = []
        
        self.print_header()
        self.build_interconnect()
        
        outfile = open(args.outpath,'w')
        outfile.write('\n'.join(self.lines))
        outfile.close()
    
if __name__ == "__main__":
    wb_builder()