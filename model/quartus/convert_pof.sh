#!/bin/bash

wine C:\\POF2JED\\bin\\POF2JED.exe -i zx50_cpld_core.pof -o zx50_cpld_core.jed
PYTHONPATH=~/git/prjbureau python3 -m util.fuseconv --device ATF1508AS zx50_cpld_core.jed zx50_cpld_core.svf
