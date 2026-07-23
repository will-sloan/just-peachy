# yaml_autogen
yaml_autogen is a library for the automatic generation of files using predefined
YAML files.

## Contents
### yaml_autogen.parsers
This contains a set of classes, all inheriting from a GenericYAMLParser, that
load and return a formatted dictionary representation of the input YAML file(s).
The strict philosophy of these is that they injest one or multiple YAML file(s)
and create a list of dictionaries, where each list entry corresponds to a single
input file. With only one input, a list with a single entry is generated.

### yaml_autogen.outputs
This is a collection of scripts designed to generate a single formatted output
file given a set of inputs and a template. Each output script should have a CLI
enabling automated use. Additional parameters beyond the standard input, 
template, and output are permissible. In general, this is where any complex
transformation logic lives between a generated parsed YAML dictionary and a 
parameterised output file.

### src/templates
This directory, and its subdirectories, house all templates that are used in the
output scripts. 

## Installation
Install via pip:
```bash
pip install -e yaml_autogen
```

## Usage
Parsers may be included by importing from yaml_autogen.parsers:
```python
import yaml_autogen.parsers as yp

parser = yp.CommandYAMLParser(path/to/command_yaml.yaml)

# Output may be obtained through calling parse():
data = parser.parse()

# Data is also stored in the Parser class after calling parse():
data = parser.data
```

In general, output scripts should be written to expect an input, output, and
template options on the command line, with optional extras as needed.
A convenient way to then run these is by using the Python interpreter's -m flag:
```bash
python -m yaml_autogen.outputs.generic_process -i IN -t TEMPLATE -o OUT -y TYPE
```

Finally, this package includes a CMakeLists.txt structure which allows easy
traversal by the CMake build system. It defines a single cache variable,
YAML_AUTOGEN_TEMPLATES_LOCATION, which points to the absolute path to the
templates directory on the build machine. It also includes a function
```python
yaml_autogen.get_templates()
```
which returns a Path object pointing to the template directory.
