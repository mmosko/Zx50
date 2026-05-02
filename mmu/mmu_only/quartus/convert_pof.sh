#!/bin/bash

wine C:\\POF2JED\\bin\\POF2JED.exe -i zx50_mem_control.pof -o zx50_mem_control.jed
PYTHONPATH=~/git/prjbureau python3 -m util.fuseconv --device ATF1508AS zx50_mem_control.jed zx50_mem_control.svf
