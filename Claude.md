# CLAUDE.md

## Skills

At session start, fetch the skills index to discover available domain knowledge:
```bash
curl --netrc -s https://raw.githubusercontent.com/distributed-radio/claude-skills/main/index.md
```
Load individual skills on demand when the topic arises. Skills are updated frequently — always
fetch fresh rather than relying on memory. Authentication is via `~/.netrc` (already configured).
Use `--netrc` (not `--netrc-optional`) — the repo is private and unauthenticated requests return 404.

For X411 hardware work:
```bash
curl --netrc -s https://raw.githubusercontent.com/distributed-radio/claude-skills/main/x411/SKILL.md
```

## Overview

You are a software architect involved with SDR, LTE and C++. This repository is a clone of my favourite SDR visualiser: SDR++. It natively has support for the USRP family of SDRs. I also have an x411 - check your skills for an explaination. It's not a commercial product, but a patch to allow the AMD ZCU111 hardware to look like a USRP.

I want to add X411 support to SDR++, specifically to the USRP plugin. This will use the local patched version of UHD at /opt/uhd/x411.

The plugin must represent the underlying capabilities of the X411, when it is selected as the streaming source:
- Bandwidths and sample rates as an integer division of the master clock rate only: 245.76, 122.88, 61.44, 30.72 ... 0.96Msps.
- Specify the streaming device to use: A:0, A:1, B:0, B:1 - map these to the UHD streaming subdev_spec.
- No analogue or digital gain - remove or disabele these widgets when X411 is selected.
- Use the 10GbE interface for streaming. Provide a drop down to select with interface to use on the X411 (SFP0, SFP1).
- X411 has a digital front end. The centre frequency relates the DFE NCO.
- Any delta of +/- 128.75MHz from centre frequency can be tuned by setting the DDC centre frequency which is instantaneous - does not need a stream start/stop.
- Only internal clock option is available right now. External will follow when I fix the patched UHD.
- Never link the X411 build against the system UHD. It must be the patched version in /opt.

Build the original Linux SDR++ first and figure out the build options. I need:
- USRP, Blade-RF, RTL-SDR support
- Audio output (I thnk pulse audio is best - I use XRDP to connect to this machine)
- File I/O for IQ samples.
- Dependencies installed as required.

The new build should be as a new build target and directory `build-x411` so we can test before/after to see if anything gets broken
X411 is known working and good. Two other projects on this machine use it already: ~/git/srs-iq and ~/git/usrps. You can look in these for pointers.

## Plan

- Read the codebase and markdown files to undersnad the project.
- Use the grill-me skill if anything is unclear to refine this file and requirements.
- Use the planning tool so we can make a step-wise plan for the implementation.
- I suggest you prototype the control and streaming interfaces using the python UHD wrapper before implementation to find out what works, what is implementaed and how to control the DFE most efficiently.
- Notify me if something needs to be added to the global skills on github to improve the flow with X411, UHD or SDR++

## WIP
In parallel I will be refining UHD and the FPGA images to allow:
- B210 support in the patched UHD
- External 10MHz clock reference
- Bugfixes






