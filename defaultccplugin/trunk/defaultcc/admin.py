# -*- coding: utf-8 -*-
#
# Copyright (C) 2009 ERCIM
# Copyright (C) 2009 Jean-Guilhem Rouel <jean-guilhem.rouel@ercim.org>
# Copyright (C) 2009 Vivien Lacourba <vivien.lacourba@ercim.org>
# Copyright (C) 2012-2015 Ryan J Ollos <ryan.j.ollos@gmail.com>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#

from genshi.builder import tag
from genshi.core import START
from genshi.filters import Transformer
from genshi.filters.transform import INSIDE

from trac.core import Component, implements
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

    implements(IEnvironmentSetupParticipant, ITemplateStreamFilter,
               IRequestFilter)

    SCHEMA = [
        Table('component_default_cc', key='name')[
            Column('name'),
            Column('cc'),
            Index(['name']),
        ]
    ]

    # IEnvironmentSetupParticipant methods

    def environment_created(self):
        self._upgrade_db()

    def environment_needs_upgrade(self, db):
        try:
            self.env.db_query("SELECT COUNT(*) FROM component_default_cc")
        except self.env.db_exc.OperationalError:  # No such table
            return True
        else:
            return False

    def upgrade_environment(self, db):
        self._upgrade_db()

    def _upgrade_db(self):
        db_backend = DatabaseManager(self.env)._get_connector()[0]
        with self.env.db_transaction as db:
            cursor = db.cursor()
            for table in self.SCHEMA:
                for stmt in db_backend.to_sql(table):
                    cursor.execute(stmt)

    # IRequestFilter methods

    def pre_process_request(self, req, handler):
        if 'TICKET_ADMIN' in req.perm and req.method == 'POST' \
                and req.path_info.startswith('/admin/ticket/components'):
            if req.args.get('save') and req.args.get('name'):
                old_name = req.args.get('old_name')
                new_name = req.args.get('name')
                old_cc = DefaultCC(self.env, old_name)
                new_cc = DefaultCC(self.env, new_name)
                new_cc.cc = req.args.get('defaultcc', '')
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
                    cc.cc = req.args.get('defaultcc', '')
                    cc.insert()
            elif req.args.get('remove'):
                if req.args.get('sel'):
                    # If only one component is selected, we don't receive
                    # an array, but a string preventing us from looping in
                    # that case.
                    if isinstance(req.args.get('sel'), basestring):
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
        if 'TICKET_ADMIN' in req.perm and \
                req.path_info.startswith('/admin/ticket/components'):
            if data.get('component'):
                cc = DefaultCC(self.env, data.get('component').name)
                filter = Transformer('//form[@class="mod"]/fieldset'
                                     '/div[@class="field"][2]')
                filter = filter.after(tag.div("Default CC:",
                                              tag.br(),
                                              tag.input(type='text',
                                                        name='defaultcc',
                                                        value=cc.cc),
                                              class_='field')) \
                               .before(tag.input(type='hidden',
                                                 name='old_name',
                                                 value=cc.name))
                return stream | filter
            else:
                filter = Transformer('//form[@id="addcomponent"]'
                                     '/fieldset/div[@class="buttons"]')
                stream |= filter.before(tag.div("Default CC:",
                                                tag.br(),
                                                tag.input(type='text',
                                                          name='defaultcc'),
                                                class_='field'))

                default_ccs = DefaultCC.select(self.env)

                stream |= Transformer('//table[@id="complist"]/thead'
                                      '/tr/th[3]') \
                          .after(tag.th('Default CC'))

                components = data.get('components')
                if components:
                    func = self._inject_default_cc_cols(default_ccs,
                                                        components)
                    stream |= Transformer('//table[@id="complist"]'
                                          '/tbody/tr').apply(func)
                return stream

        return stream

    def _inject_default_cc_cols(self, default_ccs, components):
        def fn(stream):
            idx = 0
            for mark, event in stream:
                if mark is None:
                    yield mark, event
                    continue
                kind, data, pos = event
                if kind is START:
                    if data[0].localname == 'td' and \
                            data[1].get('class') == 'default':
                        if idx < len(components):
                            component = components[idx]
                            cc = default_ccs.get(component.name) or ''
                        else:
                            cc = ''
                        idx += 1
                        for event in tag.td(cc, class_='defaultcc'):
                            yield INSIDE, event
                yield mark, (kind, data, pos)
        return fn
