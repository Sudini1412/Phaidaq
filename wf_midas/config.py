from argparse import ArgumentParser
from configparser import ConfigParser
import copy
import io
import numpy as np
import os
import pkgutil
import shlex
import sys
from matplotlib.backends.backend_pdf import PdfPages


class Config:
  """Configuration file. See main program of config.py for example usage.
  Notes: 
    In Python, a double underscore at the start means private method.
    Static methods are used when there is no dependence of the function on class variables.
  """

  def __init__(self, default='config.ini', is_req_input=True, is_req_output=False, cmdline_args=None):
    """Constructor.
    Args:
      default (str, dict): default configuration file name or dictionary
      is_req_input (bool): control if input file name is required as a command line argument
      is_req_output (bool): control if output file name is required as a command line argument
      cmdline_args (str, None): primarily for use with Jupyter notebooks
        None: command line arguments are parsed standardly
        str: command line arguments are ignored and this string is parsed instead
        cmdline_args="-c config_fname.ini -p base:nevents:5"
    """
    # Read default config file
    print('Reading default config file: config.ini')
    self.__config = self.__parse_config('config/config.ini', check_wd=True)

    # Parse command line arguments and convert to dictionary format
    parser = ArgumentParser()
    parser.add_argument('-c', '--config', help='configuration file name used to update default parameters with .ini extention')
    parser.add_argument('-e', '--events', nargs='+', type=int, help='list of event numbers')
    parser.add_argument('-i', '--input', nargs='+', required=is_req_input, help='input file name (fil format) with .fil extention')
    parser.add_argument('-o', '--output', required=is_req_output, help='output file name (wav or root format) without extention')
    parser.add_argument('-p', '--pars', nargs='+', default=[], help='configuration option in section s, name n, value v (in case of spaces quotes are needed)')
    parser.add_argument('-r', '--run', type=int, help='run number', default=-1)
    parser.add_argument('-v', '--view', action='store_true', help='viewer to create pdf')
    parser.add_argument('-n', '--nevent',type = int, help='number of events to reconstruct')
    if cmdline_args is None:
      args = vars(parser.parse_args())
    else:
      args = vars(parser.parse_args(shlex.split(cmdline_args)))

    # Set class attributes
    self.events       = args['events']
    self.nevents      = args['nevent']
    self.input        = []
    self.output       = args['output']
    self.run          = args['run']
    self.is_req_input = is_req_input

    if args['config'] is not None:  # Update if config file specified as command line argument
      print(f"Reading config file: {args['config']}")
      self.update(args['config'], check_wd=True)
    else:  # Check for config file with name of main script in pyreco/config/
      import __main__
      exe_name = os.path.basename(__main__.__file__).split('.')[0] + '.ini'
      print(f"Reading config file: {exe_name}")
      try:
        self.update(exe_name, check_wd=False)
      except FileNotFoundError:
        pass

    # Update configuration with command line arguments (set with -p flag)
    for par in args['pars']:
      s, k, v = self.__parse_skv(par)
      self.__config.set(s, k, v)

    if self.is_req_input:
      for fin in args['input']:
        # Check if input exists (directory or file)
        if os.path.isdir(fin):
          self.input = fin # leave red usage unchaged
          if self.run < 0:
            print(f'Run number not set, using dummy value {self.run}')
          print(f'Processing one directory {fin} from the input')
          break
        elif os.path.isfile(fin):
          self.input.append(fin) # midas usage
        else:
           raise FileNotFoundError(f"Input file not found: {fin}")

    # Optionally set random seed
    if 'seed' in self('base'):
      np.random.seed(self('base', 'seed', 'int'))

    # Write configuration to PDF
    self.pdf = None
    if args['view']:
      self.pdf = PdfPages(f'{self.output}.pdf')
      d = self.pdf.infodict()
      d['Title'] = 'test pdf writer'

  def __call__(self, section=None, key=None, dtype='str'):
    """Used to return configuration dictionary sections or values and prevent modification."""
    if section is None:  # All keys in all sections
      return copy.deepcopy(self.__config._sections)  # Prevent modification
    elif key is None:  # All keys in specified section
      return dict(self.__config.items(section))
    elif dtype == 'bool':  # Value of key in section cast as bool
      return self.__config.getboolean(section, key)
    elif dtype == 'int':  # Value of key in section cast as int
      return self.__config.getint(section, key)
    elif dtype == 'float':  # Value of key in section cast as float
      return self.__config.getfloat(section, key)
    elif dtype == 'str':  # Value of key in section as default (string)
      return self.__config.get(section, key)
    elif dtype == 'eval':  # Evaluate key string as if pasting in terminal (this is dangerous for untrusted sources)
      return eval(self.__config.get(section, key))
    else:
      raise ValueError(f"Value dtype '{dtype}' not implemented.")

  def __str__(self):
    """Output when printing an instance of this class."""
    return f"<Config: {str(self.__config._sections)}>"

  def update(self, source, **kwargs):
    """Update configuration parameters with a file name or dictionary.
    Args:
      source (str, dict): configuration file name or dictionary
      *kwargs: keyword arguments passed to __parse_config()
    """
    print('Updating configuration parameters.')
    c = self.__parse_config(source, **kwargs)
    for sect in c.sections():  # Update values in configuration dictionary
      for key, val in c.items(sect):
        self.__config.set(sect, key, val)

  @staticmethod
  def __parse_config(source, check_wd=True):
    """Parse configuration file or dictionary.
    Args:
      source (str, dict): configuration file name or dictionary
      check_wd (bool): only used if source is a string
        True: the current working directory is first searched for the file and then the config directory is searched
        False: only the config directory is searched for the file
    """
    parser = ConfigParser(inline_comment_prefixes='#')
    if isinstance(source, dict):
      parser.read_dict(source)
    elif isinstance(source, str):
      if check_wd and os.path.isfile(source):  # First check working directory
        parser.read(source)
      else:  # Now check pyreco config folder
        try:
          c = pkgutil.get_data('pyreco', f'config/{source}')
          parser.read_file(io.StringIO(c.decode('utf-8')))
        except:
          raise FileNotFoundError(f"Configuration file '{source}' not found in " + check_wd*"current directory or " + "pyreco config folder.")
    else:
      raise TypeError(f"Source type '{type(source)}' not implemented.")
    return parser

  @staticmethod
  def __parse_skv(skv):
    """Parse section, key, and value from s:k:v command line input."""
    if skv.count(':') != 2:
      raise ValueError(f"Parameter option '{skv}' is formatted incorrectly. The required format is 'section:key:value'.")
    s, k, v = skv.split(':')
    return s.strip(), k.strip(), v.strip()  # Remove leading+trailing spaces


if __name__ == '__main__':
  """Demonstrate usage of Config class.
  To run:
    python manager/config.py
    python manager/config.py -i out_ds20k.fil -o test
    python manager/config.py -p base:nevents:5 daq:n_channels:25
    python manager/config.py -p "base : nevents : 5" "
  """
  config = Config(is_req_input=False, is_req_output=False)

  print(f"\ninput: {config.input}\noutput: {config.output}\n")

  # Default value
  print('Read default (config.ini).')
  print('  base : nevents =', config('base', 'nevents', 'int'), '\n')

  # Update with file
  fname = 'ds20k.ini'
  config.update(fname)
  print('Read ds20k.ini.')
  print('  base : nevents =', config('base', 'nevents', 'int'), '\n')

  # How NOT to change value in section
  section = config('base')
  section['nevents'] = '100'
  print('Try to change value in section. See how it fails.')
  print('  base : nevents =', config('base', 'nevents', 'int'), '\n')

  # Correctly change value in section
  pars = {
    'base': {
      'nevents': '100',
    },
  }
  config.update(pars)
  print('Correctly change value in section.')
  print('  base : nevents =', config('base', 'nevents', 'int'), '\n')

  # Get section
  print('Get section.')
  print(config('base'), '\n')

  # Get all sections
  print('Get all sections.')
  print(config(), '\n')

  # Dump full configuration file
  print('Print full configuration.')
  print(config, '\n')
