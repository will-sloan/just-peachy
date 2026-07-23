# Copyright 2022-2024 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.
import argparse
import re
import yaml

from pathlib import Path

## File containing the list of default parameters used in the XMOS product
XMOS_DEFAULTS_FILE_PATH = Path( __file__ ).parent  / "yaml_files/settings_and_defaults/product/control_param_values.yaml"
## List of SHF commands whose default values have been updated by XMOS
OVERRIDDEN_DEFAULT_LIST = [ 'PP_AGCDESIREDLEVEL', 'PP_AGCFASTTIME', 'PP_DTSENSITIVE', 'PP_NLATTENONOFF' ]
## List of AEC SHF commands defined after the PP commands
AEC_CMDS_AFTER_PP = [ 'ASROUTGAIN', 'ASROUTONOFF', 'FIXEDBEAMSONOFF', 'FIXEDBEAMNOISETHR' ]

def convert_boolean(value):
    """Convert on/off values into True/False
    Args:
      value:
        value to convert
    """

    if value == 'on':
        return 'True'
    elif value == 'off':
        return 'False'
    else:
        return value

class CmdFields():
    """List of fields for each command"""

    def __init__(self):
        """Init function"""

        self.name = ""
        self.index = ""
        self.define = ""
        self.help = ""
        self.value = ""
        self.type = ""
        self.value_type = ""
        self.number_of_values = ""
        self.default_value = ""
        self.value_ranges = ""
        self.hidden = "false"

class CmdParser():
    """Variables and functions to extract command fields"""

    def __init__(self):
        """Init function"""

        self.cmd_found = 0
        self.all_info = ""
        self.fields = CmdFields()
        self.first_lines_written = 0
        self.aec_cmds_completed = 0
        self.done = 0

    def update_info(self, line):
        """Collect all the information from the command description

        Args:
          line:
            text to parse
        """

        if not self.cmd_found:
            s = re.search("\/\*\s?([A-Z_0-9]+)\s?:\s?(.*)\*\/", line)
            if s:
                # Set the prefix of the current command name.
                prefix = "AEC_"
                # Some AEC commands are defined after the PP commands, so keep the AEC_ prefix
                if self.aec_cmds_completed and not any(cmd == s.group(1) for cmd in AEC_CMDS_AFTER_PP):
                    prefix = "PP_"
                self.fields.name = prefix + s.group(1)
                self.all_info = s.group(2).strip() + " "

                if "NUMPARS" in self.fields.name:
                    self.done = 1
                self.cmd_found = 1
        else:
            self.all_info += line.replace("/* ", "").replace("*/", "").strip() + " "

    def update_define(self, string):
        """Write the define of the command

        Args:
          string:
            string containing text to write
        """

        self.fields.define = string.strip()

    def check_if_desired(self, prefix):
        """Check the type of the command (AEC or PP) and discard if undesired

        Args:
          None

        Returns:
          desired: bool
            True if command is desired, False if undesired
        """

        desired = True
        if prefix == "AEC" and "_AEC_" not in self.fields.define:
            desired = False
        elif prefix == "PP" and "_PP_" not in self.fields.define:
            desired = False
        return desired


    def update_index(self, string):
        """Write the index of the command

        Args:
          string:
            string containing text to write
        """


        self.fields.index = string.strip()

    def update_type(self):
        """Extract and write the type of the command"""

        pattern = r"\s*\((((write)|(read)-only)|(read-write))\)\s*"
        s = re.search(pattern, self.all_info)
        if s:
            self.fields.type = "CMD_"+s.group(1).upper().replace("-", "_")
        # The command AEC_FIXEDBEAMNOISETHR doesn't define the type,
        # we need to hardcode this value.
        if self.fields.name == "AEC_FIXEDBEAMNOISETHR":
            self.fields.type = "CMD_READ_WRITE"
        if not self.fields.type:
            print( f"Error: type for command {self.fields.name} not found")
            return 1
        self.all_info = re.sub(pattern, "", self.all_info)

    def update_value_type(self):
        """Extract and write the value type of the command"""

        VALUE_TYPE_CONVERSION = {"FLOAT1":"TYPE_FLOAT", "INT":"TYPE_INT32"}

        pattern = r"\s*type[:,]? (\w+)(\[(\d)\])?,?\s*"
        s = re.search(pattern, self.all_info)
        if s:
            self.fields.value_type = VALUE_TYPE_CONVERSION[s.group(1)]
            if s.group(2):
                self.fields.number_of_values = s.group(3)
            # The command AEC_FIXEDBEAMNOISETHR has type `FLOAT1[BECLEAR_NUMBER_OF_BEAMS]`
            # As it uses a define for the number of values, we need to hardcode this value.
            elif self.fields.name == "AEC_FIXEDBEAMNOISETHR":
                self.fields.number_of_values = str(2)
            else:
                self.fields.number_of_values = str(1)
        self.all_info =  re.sub(pattern, "", self.all_info)

    def update_default_value(self, xmos_default_values):
        """Extract and write the default value of the command

           If the value is not listed, use 'NA'

        Args:
          xmos_default_values:
            list containing control commands with the corresponding XMOS default value
        """

        shf_default_value = "NA"
        pattern = r"\s*\(default: ([\w\.\-\(\),]+)\),?\s*"
        s = re.search(pattern, self.all_info)
        if s:
            param_found = 0
            shf_default_value = s.group(1)
            ## Check default value is the same as the XMOS one:
            ## Do not check:
            ##    - read-only parameters
            ##    - parameters whose default values are overriden
            if self.fields.type != 'CMD_READ_ONLY' and self.fields.name not in OVERRIDDEN_DEFAULT_LIST:
                for param in xmos_default_values:
                    if param['cmd'] == self.fields.name:
                        param_found = 1
                        ## 'on/off' values must converted be converted into 'True/False',
                        ## as this is what happens in load() function of the yaml package
                        if str(param['default_value']) != convert_boolean(shf_default_value):
                            print(f"Modified default value for command {self.fields.name}: XMOS value - {param['default_value']}, original value - {shf_default_value}")
                        break
                if param_found != 1:
                    print( f"Error: XMOS default value for command {self.fields.name} not found")
                    return 1

        self.fields.default_value = shf_default_value
        self.all_info =  re.sub(pattern, "", self.all_info)

    def update_value_ranges(self, cmd_name):
        """Extract and write the value range of the command

           The format of this information varies greatly between commands

        Args:
          cmd_name:
            full name of the command to parse

        """
        value_ranges_str = ""

        # Handle outliers
        if cmd_name.strip() == "BECLEAR_SUPERHANDSFREE_PP_MGSCALE":
            # Original text: /* type: FLOAT1[3] (max,min,cur), values (max,min): [(1.0,0.0) .. (1e5,max)]  */
            #                /* (default: (1.0,1.0)), values (cur): min or max (read-only).                */
            value_ranges_str =  "\n          value0: [1.0 .. 1e5]"
            value_ranges_str += "\n          value1: [0.0 .. value0]"
            value_ranges_str += "\n          value2: any"
        elif cmd_name.strip() == "BECLEAR_SUPERHANDSFREE_AEC_AECSILENCELEVEL":
            # Original text: /* type: FLOAT1[2] (set,cur), values (set): [0.0 .. 1.0] (default: 1e-8f),    */
            #                /* values (cur): 0.05*set, 1e-6f or set (read-only).                          */
            value_ranges_str =  "\n          value0: [0.0 .. 1.0]"
            value_ranges_str += "\n          value1: any"
        elif cmd_name.strip() == "BECLEAR_SUPERHANDSFREE_AEC_FIXEDBEAMNOISETHR":
            # Original text: /*   type: FLOAT1[BECLEAR_NUMBER_OF_BEAMS], values: [0.0 .. 1.0] (default: 0.4) */
            value_ranges_str =  "\n          value0: [0.0 .. 1.0]"
            value_ranges_str += "\n          value1: [0.0 .. 1.0]"
        # Handle generic case
        else:
            pattern_interval = r"values:? (\[.*\])"
            pattern_single_values = r"values:? ((\w+,){1,}\w+)"
            s = re.search(pattern_interval, self.all_info)
            if s:
                value_ranges_str = s.group(1)
                value_ranges_str = f"\n          value0: {value_ranges_str}"
            else:
                s = re.search(pattern_single_values, self.all_info)
                if s:
                    value_ranges_str = s.group(1)
                    values_list = [int(x) for x in value_ranges_str.split(",")]
                    # All the values are integers, as float number won't be parsed in the regex
                    # Check if all the values are consecutive numbers
                    if sorted(values_list) != list(range(min(values_list), max(values_list)+1)):
                        print(f"Error: Values in list are not consecutive numbers: {values_list}")
                        return 1

                    value_ranges_str = f"[{min(values_list)} .. {max(values_list)}]"
                    value_ranges_str = f"\n          value0: {value_ranges_str}"
                else:
                    print(f"Error: cannot parse value range: {self.all_info}")
                    return 1
        self.fields.value_ranges = value_ranges_str
        self.all_info = self.all_info.replace("values", " Valid range")

    def start_file(self, fd, prefix):
        """Check if the first command has been found and initialize yaml file

        Args:
          fd:
            file descriptor of output yaml file
        """

        if not self.first_lines_written:
            string_start = f"#AUTOGENERATED. DO NOT EDIT\n\n"

            if prefix == 'AEC' or prefix == 'BOTH':
                string_start += "AEC_RESID:\n"
            else:
                string_start += 'PP_RESID:\n'
                self.aec_cmds_completed = 1
            string_start += "   dedicated_commands:\n"

            fd.write(string_start)
            self.first_lines_written = 1

    def check_if_aec_cmds_completed(self, fd):
        """Check if AEC commands are all parsed and update yaml output file

        Args:
          fd:
            file descriptor of output yaml file
        """

        if not self.aec_cmds_completed and "_PP_" in self.fields.define:
            fd.write(f"PP_RESID:\n  dedicated_commands:\n")
            self.aec_cmds_completed = 1
            # Update the prefix of the current command name
            self.fields.name = self.fields.name.replace("AEC_", "PP_")

    def write_cmd(self, fd):
        """Write all the information about the command to the yaml file

        Args:
          fd:
            file descriptor of output yaml file
        """

        fd.write(f"    - cmd: {self.fields.name}\n")
        fd.write(f"      define: {self.fields.define}\n")
        fd.write(f"      index: {self.fields.index}\n")
        fd.write(f"      type: {self.fields.type}\n")
        fd.write(f"      value_type: {self.fields.value_type}\n")
        fd.write(f"      number_of_values: {self.fields.number_of_values}\n")
        fd.write(f"      default_value: {self.fields.default_value}\n")
        fd.write(f"      value_ranges:{self.fields.value_ranges}\n")
        fd.write(f"      help: \"{self.all_info.strip()}\"\n")
        fd.write(f"      hidden: {self.fields.hidden}\n")

    def reset(self):
        """Reset variables"""

        self.cmd_found = 0
        self.all_info = ""
        self.fields = CmdFields()

def generate_shf_yaml(shf_header_file, shf_yaml_file, shf_prefix_target):
    """Parse header file and generate yaml file"""

    ## Load XMOS default values
    if not XMOS_DEFAULTS_FILE_PATH.exists():
        print("Error: No SHF defaults file found.")
        return 1
    f = open(XMOS_DEFAULTS_FILE_PATH)
    data = yaml.safe_load(f)

    ## Flatten list of default values
    xmos_default_values = []
    for _, value in data.items():
        xmos_default_values += value

    with open(shf_header_file) as h_file:
        lines = h_file.readlines()
        cmd_parser = CmdParser()
        cmd_found = 0
        with open(shf_yaml_file, "w") as y_file:
            for line in lines:
                if line.startswith("/*") and re.search('[a-zA-Z0-9]', line):
                    cmd_parser.update_info(line)
                    if cmd_parser.done:
                        return 0

                s = re.search("#define\s+(BECLEAR_.*)\s+(\d+)", line)
                if s:
                    cmd_parser.start_file(y_file, shf_prefix_target)
                    cmd_parser.update_define(s.group(1))
                    if cmd_parser.check_if_desired(shf_prefix_target):
                        cmd_parser.check_if_aec_cmds_completed(y_file)
                        cmd_parser.update_index(s.group(2))
                        cmd_parser.update_type()
                        ret = cmd_parser.update_default_value(xmos_default_values)
                        if ret:
                            return ret
                        cmd_parser.update_value_type()
                        ret = cmd_parser.update_value_ranges(s.group(1))
                        if ret:
                            return ret
                        cmd_parser.write_cmd(y_file)
                    cmd_parser.reset()
                    cmd_found = 1
        if cmd_found != 1:
            print(f"Error: file {shf_header_file} didn't contain any control command")
            return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Extract information about SHF control command to generate yaml file")
    parser.add_argument('--shf-header-file', '-i',
                        help='input header file containing SHF control commands',
                        default=Path( __file__ ).resolve().parents[2] / "modules/fwk_xvf/modules/xshf/modules/shf/inc/BeClearSuperHandsFree.h")
    parser.add_argument('--shf-yaml-file', '-o',
                        help='output yaml file containing SHF control commands',
                        default="shf_cmds.yaml")
    parser.add_argument('--shf-prefix-target', '-p',
                        help='process AEC commands, PP commands, or both. Default is both.',
                        choices=('AEC','PP','both'),
                        default='both')

    args = parser.parse_args()
    if not Path(args.shf_header_file).is_file():
        print(f"Error: file {args.shf_header_file} not found")
        exit(1)
    generate_shf_yaml(Path(args.shf_header_file), Path(args.shf_yaml_file), args.shf_prefix_target.upper())
