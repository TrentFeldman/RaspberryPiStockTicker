# Builds the C++ programs on the Pi: `make`.
#
#   ticker/ticker   the LED ticker (source: ticker/src/, starts at main.cpp)
#   calibrate       interactive panel calibration (writes panel.conf)
#   white_screen    hardware test: the whole panel one colour
#
# All link the S-PWM LED library, cloned next to this folder (../matrix-pwm-test);
# override with `make RGB_DIR=/path/to/it`. The paths below are baked in as
# absolute paths so the programs work from any directory and under sudo.

RGB_DIR ?= $(abspath $(CURDIR)/../matrix-pwm-test)
CXXFLAGS = -O2 -std=c++17 -Wall -I$(RGB_DIR)/include -DFONT_DIR='"$(RGB_DIR)/fonts/"' \
           -DSPWM_PROFILES='"$(RGB_DIR)/lib/spwm/registertest/data"' \
           -DPANEL_CONF='"$(CURDIR)/panel.conf"' -DFONTS_CONF='"$(CURDIR)/fonts.conf"'
LDLIBS = $(RGB_DIR)/lib/librgbmatrix.a -lrt -lm -lpthread -ldl

# The ticker is one program: main.cpp includes all of its headers.
TICKER_SRC = ticker/src/main.cpp $(wildcard ticker/src/*.h)

all: white_screen calibrate ticker/ticker

white_screen: white_screen.cpp panel.h
	$(CXX) $(CXXFLAGS) -o $@ $< $(LDLIBS)

calibrate: calibrate.cpp panel.h term.h
	$(CXX) $(CXXFLAGS) -o $@ $< $(LDLIBS)

ticker/ticker: $(TICKER_SRC) panel.h
	$(CXX) $(CXXFLAGS) -I. -o $@ ticker/src/main.cpp $(LDLIBS)

clean:
	rm -f white_screen calibrate ticker/ticker
