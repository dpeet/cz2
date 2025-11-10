#!/usr/bin/perl

use strict;
use IO::Termios;

$| = 1;

my $fh    = IO::Termios->open ("/dev/ttyUSB0", "9600,8,n,1") or die $!;
my $count = 0;

while (1) {
  my $check = $fh->sysread (my $read, 16);
  die $! unless defined $check;

  for my $byte (split //, $read) {
    printf "%02x ", ord $byte;

    $count++;
    if ($count == 16) {
      print "\n";
      $count = 0;
    }
  }
}
