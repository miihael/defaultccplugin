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

from genshi.builder import tag
from genshi.filters import Transformer
from trac.core import *
from trac.db import Column, DatabaseManager, Index, Table
from trac.env import IEnvironmentSetupParticipant
from trac.resource import ResourceNotFound
from trac.ticket import model
from trac.web.api import IRequestFilter, ITemplateStreamFilter

from defaultcc.model import DefaultCC

class DefaultCCAdmin(Component):
    """Allows to setup a default CC list per component through the component
    admin UI.
    """

    implements(IEnvironmentSetupParticipant, ITemplateStreamFilter, IRequestFilter)

    # IEnvironmentSetupParticipant implementation
    SCHEMA = [
        Table('component_default_cc', key='name')[
            Column('name'),
            Column('cc'),
            Index(['name']),
            ]
        ]

    def environment_created(self):
        self._upgrade_db(self.env.get_db_cnx())

    def environment_needs_upgrade(self, db):
        cursor = db.cursor()
        try:
            cursor.execute("select count(*) from component_default_cc")
            cursor.fetchone()
            return False
        except:
            return True

    def upgrade_environment(self, db):
        self._upgrade_db(db)

    def _upgrade_db(self, db):
        try:
            db_backend, _ = DatabaseManager(self.env)._get_connector()
            cursor = db.cursor()
            for table in self.SCHEMA:
                for stmt in db_backend.to_sql(table):
                    self.log.debug(stmt)
                    cursor.execute(stmt)
                    db.commit()
        except Exception, e:
            self.log.error(e, exc_info=True)
            raise TracError(str(e))

    # IRequestFilter methods

    def pre_process_request(self, req, handler):
        if 'TICKET_ADMIN' in req.perm and req.method == 'POST' and req.path_info.startswith('/admin/ticket/components'):
            if req.args.get('save') and req.args.get('name'):
                old_name = req.args.get('old_name')
                new_name = req.args.get('name')
                old_cc = DefaultCC(self.env, old_name)
                new_cc = DefaultCC(self.env, new_name)
                new_cc.cc = req.args.get('defaultcc')
                if old_name == new_name:
                    old_cc.delete()
                    new_cc.insert()
                else:
                    try:
                        model.Component(self.env, new_name)
                    except ResourceNotFound:
                        old_cc.delete()
                        new_cc.insert()
            elif req.args.get('add') and req.args.get('name'):
                name = req.args.get('name')
                try:
                    model.Component(self.env, name)
                except ResourceNotFound:
                    cc = DefaultCC(self.env, name)
                    cc.name = name
                    cc.cc = req.args.get('defaultcc')
                    cc.insert()
            elif req.args.get('remove'):
                if req.args.get('sel'):
                    # If only one component is selected, we don't receive an array, but a string
                    # preventing us from looping in that case :-/
                    if isinstance(req.args.get('sel'), unicode) or isinstance(req.args.get('sel'), str):
                        cc = DefaultCC(self.env, req.args.get('sel'))
                        cc.delete()
                    else:
                        for name in req.args.get('sel'):
                            cc = DefaultCC(self.env, name)
                            cc.delete()
        return handler

    def post_process_request(self, req, template, data, content_type):
        if template == 'admin_components.html' and 'components' in data:
            # Prior to Trac 1.0.2-r11919, components was a generator and
            # expanding the generator causes the table to not be rendered
            data['components'] = list(data['components'])
        return template, data, content_type

    # ITemplateStreamFilter methods

    def filter_stream(self, req, method, filename, stream, data):
        if 'TICKET_ADMIN' in req.perm and req.path_info.startswith('/admin/ticket/components'):
            if data.get('components'):
                filter = Transformer('//form[@id="addcomponent"]/fieldset/div[@class="buttons"]')
                stream = stream | filter.before(tag.div("Default CC:",
                                                tag.br(),
                                                tag.input(type='text', name='defaultcc'),
                                                class_='field'))

                default_ccs = DefaultCC.select(self.env)

                stream = stream | Transformer('//table[@id="complist"]/thead/tr') \
                    .append(tag.th('Default CC'))

                for i, comp in enumerate(data.get('components')):
                    if comp.name in default_ccs:
                        default_cc = default_ccs[comp.name]
                    else:
                        default_cc = ''
                    filter = Transformer('//table[@id="complist"]/tbody/tr[%d]' % (i + 1))
                    stream |= filter.append(tag.td(default_cc, class_='defaultcc'))
                return stream

            elif data.get('component'):
                cc = DefaultCC(self.env, data.get('component').name)
                filter = Transformer('//form[@id="modcomp"]/fieldset/div[@class="buttons"]')
                filter = filter.before(tag.div("Default CC:",
                                               tag.br(),
                                               tag.input(type='text', name='defaultcc', value=cc.cc),
                                               class_='field')) \
                                               .before(tag.input(type='hidden', name='old_name', value=cc.name))
                return stream | filter

        return stream
