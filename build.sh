#!/bin/bash

python jemdoc.py -c mysite.conf index.jemdoc
python jemdoc.py -c mysite.conf research.jemdoc
python jemdoc.py -c mysite.conf projects.jemdoc
python jemdoc.py -c mysite.conf publications.jemdoc
python jemdoc.py -c mysite.conf teaching.jemdoc  
