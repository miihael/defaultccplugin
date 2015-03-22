# -*- coding: utf-8 -*-
#
# Copyright (C) 2009 ERCIM
# Copyright (C) 2009 Jean-Guilhem Rouel <jean-guilhem.rouel@ercim.org>
# Copyright (C) 2009 Vivien Lacourba <vivien.lacourba@ercim.org>
# Copyright (C) 2012 Ryan J Ollos <ryan.j.ollos@gmail.com>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#

import re


class DefaultCC(object):
    """Class representing components' default CC lists
    """

    def __init__(self, env, name=None):
        self.env = env
        self.log = self.env.log
        self.name = name
        self.cc = None
        if name:
            for cc, in self.env.db_query("""
                    SELECT cc FROM component_default_cc WHERE name=%s
                    """, (name,)):
                self.cc = cc or None

    def delete(self, db=None):
        self.log.info("Deleting component %s's default CC" % self.name)
        self.env.db_transaction("""
            DELETE FROM component_default_cc WHERE name=%s
            """, (self.name,))

    def insert(self, db=None):
        assert self.name, "Cannot create default CC for a component" \
                          " without a name"

        self.log.debug("Creating %s's default CC" % self.name)
        self.env.db_transaction("""
            INSERT INTO component_default_cc (name,cc) VALUES (%s,%s)
            """, (self.name, _fixup_cc_list(self.cc)))

    @classmethod
    def select(cls, env, db=None):
        res = {}
        for name, cc in env.db_query("""
                SELECT name,cc FROM component_default_cc ORDER BY name
                """):
            res[name] = cc
        return res


def _fixup_cc_list(cc_value):
    """Fix up cc list separators and remove duplicates."""
    # Copied from trac.ticket.model
    cclist = []
    for cc in re.split(r'[;,\s]+', cc_value):
        if cc and cc not in cclist:
            cclist.append(cc)
    return ', '.join(cclist)
