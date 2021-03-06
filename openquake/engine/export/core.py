# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2010-2016 GEM Foundation
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake. If not, see <http://www.gnu.org/licenses/>.

"""Functions for getting information about completed jobs and
calculation outputs, as well as exporting outputs from the database to various
file formats."""


import os
import zipfile

from openquake.commonlib.export import export
from openquake.commonlib import datastore
from openquake.engine import logs


class DataStoreExportError(Exception):
    pass


def zipfiles(fnames, archive):
    """
    Build a zip archive from the given file names.

    :param fnames: list of path names
    :param archive: path of the archive
    """
    z = zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, allowZip64=True)
    for f in fnames:
        z.write(f, os.path.basename(f))
    z.close()


def export_from_datastore(output_key, calc_id, datadir, target):
    """
    :param output_key: a pair (ds_key, fmt)
    :param calc_id: calculation ID
    :param datadir: directory containing the datastore
    :param target: directory, temporary when called from the engine server
    """
    makedirs(target)
    ds_key, fmt = output_key
    dstore = datastore.read(calc_id, datadir=datadir)
    dstore.export_dir = target
    try:
        exported = export(output_key, dstore)
    except KeyError:
        raise DataStoreExportError(
            'Could not export %s in %s' % output_key)
    if not exported:
        raise DataStoreExportError(
            'Nothing to export for %s' % ds_key)
    elif len(exported) > 1:
        # NB: I am hiding the archive by starting its name with a '.',
        # to avoid confusing the users, since the unzip files are
        # already in the target directory; the archive is used internally
        # by the WebUI, so it must be there; it would be nice not to
        # generate it when not using the Web UI, but I will leave that
        # feature for after the removal of the old calculators
        archname = '.' + ds_key + '-' + fmt + '.zip'
        zipfiles(exported, os.path.join(target, archname))
        return os.path.join(target, archname)
    else:  # single file
        return exported[0]

#: Used to separate node labels in a logic tree path
LT_PATH_JOIN_TOKEN = '_'


def makedirs(path):
    """
    Make all of the directories in the ``path`` using `os.makedirs`.
    """
    if os.path.exists(path):
        if not os.path.isdir(path):
            # If it's not a directory, we can't do anything.
            # This is a problem
            raise RuntimeError('%s already exists and is not a directory.'
                               % path)
    else:
        os.makedirs(path)


def export_outputs(job_id, target_dir, export_types):
    # make it possible commands like `oq-engine --eos -1 /tmp`
    datadir, dskeys = logs.dbcmd('get_results', job_id)
    if not dskeys:
        yield('Found nothing to export for job %s' % job_id)
    for dskey in dskeys:
        yield('Exporting %s...' % dskey)
        for line in export_output(
                dskey, job_id, datadir, target_dir, export_types):
            yield line


def get_outkey(dskey, export_types):
    """
    Extract the first pair (dskey, exptype) found in export
    """
    for exptype in export_types:
        if (dskey, exptype) in export:
            return (dskey, exptype)


def export_output(dskey, calc_id, datadir, target_dir, export_types):
    """
    Simple UI wrapper around
    :func:`openquake.engine.export.core.export_from_datastore` yielding
    a summary of files exported, if any.
    """
    outkey = get_outkey(dskey, export_types.split(','))
    if not outkey:
        yield 'There is not exporter for %s, %s' % (dskey, export_types)
        return
    the_file = export_from_datastore(outkey, calc_id, datadir, target_dir)
    if the_file.endswith('.zip'):
        dname = os.path.dirname(the_file)
        fnames = zipfile.ZipFile(the_file).namelist()
        yield('Files exported:')
        for fname in fnames:
            yield(os.path.join(dname, fname))
    else:
        yield('File exported: %s' % the_file)
