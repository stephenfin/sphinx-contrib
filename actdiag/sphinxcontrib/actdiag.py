# -*- coding: utf-8 -*-
"""
    actdiag.sphinx_ext
    ~~~~~~~~~~~~~~~~~~~~

    Allow actdiag-formatted diagrams to be included in Sphinx-generated
    documents inline.

    :copyright: Copyright 2010 by Takeshi Komiya.
    :license: BSDL.
"""

import io
import os
import re
import posixpath
import traceback
from collections import namedtuple
try:
    from hashlib import sha1 as sha
except ImportError:
    from sha import sha

from docutils import nodes
from sphinx.errors import SphinxError
from sphinx.util.osutil import ensuredir

import actdiag_sphinxhelper as actdiag
u = actdiag.utils.compat.u


class ActdiagError(SphinxError):
    category = 'Actdiag error'


class Actdiag(actdiag.utils.rst.directives.ActdiagDirective):
    def run(self):
        try:
            return super(Actdiag, self).run()
        except actdiag.core.parser.ParseException as e:
            if self.content:
                msg = '[%s] ParseError: %s\n%s' % (self.name, e, "\n".join(self.content))
            else:
                msg = '[%s] ParseError: %s\n%r' % (self.name, e, self.arguments[0])

            reporter = self.state.document.reporter
            return [reporter.warning(msg, line=self.lineno)]

    def node2image(self, node, diagram):
        return node


def get_image_filename(self, code, format, options, prefix='actdiag'):
    """
    Get path of output file.
    """
    if format.upper() not in ('PNG', 'PDF', 'SVG'):
        raise ActdiagError('actdiag error:\nunknown format: %s\n' % format)

    if format.upper() == 'PDF':
        try:
            import reportlab
        except ImportError:
            msg = 'actdiag error:\n' + \
                  'colud not output PDF format; Install reportlab\n'
            raise ActdiagError(msg)

    hashkey = (code + str(options)).encode('utf-8')
    fname = '%s-%s.%s' % (prefix, sha(hashkey).hexdigest(), format.lower())
    if hasattr(self.builder, 'imgpath'):
        # HTML
        relfn = posixpath.join(self.builder.imgpath, fname)
        outfn = os.path.join(self.builder.outdir, '_images', fname)
    else:
        # LaTeX
        relfn = fname
        outfn = os.path.join(self.builder.outdir, fname)

    if os.path.isfile(outfn):
        return relfn, outfn

    ensuredir(os.path.dirname(outfn))

    return relfn, outfn


def get_fontmap(self):
    FontMap = actdiag.utils.fontmap.FontMap

    try:
        fontmappath = self.builder.config.actdiag_fontmap
        fontmap = FontMap(fontmappath)
    except:
        attrname = '_actdiag_fontmap_warned'
        if not hasattr(self.builder, attrname):
            msg = ('actdiag cannot load "%s" as fontmap file, '
                   'check the actdiag_fontmap setting' % fontmappath)
            self.builder.warn(msg)
            setattr(self.builder, attrname, True)

        fontmap = FontMap(None)

    try:
        fontpath = self.builder.config.actdiag_fontpath
        if isinstance(fontpath, actdiag.utils.compat.string_types):
            fontpath = [fontpath]

        if fontpath:
            config = namedtuple('Config', 'font')(fontpath)
            _fontpath = actdiag.utils.bootstrap.detectfont(config)
            fontmap.set_default_font(_fontpath)
    except:
        attrname = '_actdiag_fontpath_warned'
        if not hasattr(self.builder, attrname):
            msg = ('actdiag cannot load "%s" as truetype font, '
                   'check the actdiag_fontpath setting' % fontpath)
            self.builder.warn(msg)
            setattr(self.builder, attrname, True)

    return fontmap


def get_anchor(self, refid, fromdocname):
    for docname in self.builder.env.found_docs:
        doctree = self.builder.env.get_doctree(docname)
        for target in doctree.traverse(nodes.Targetable):
            if target.attributes.get('refid') == refid:
                targetfile = self.builder.get_relative_uri(fromdocname, docname)
                return targetfile + "#" + refid


def resolve_reference(self, href, options):
    if href is None:
        return
    pattern = re.compile(u("^:ref:`(.+?)`"), re.UNICODE)
    matched = pattern.search(href)
    if matched:
        return get_anchor(self, matched.group(1), options.get('current_docname', ''))
    else:
        return href


def create_actdiag(self, code, format, filename, options, prefix='actdiag'):
    """
    Render actdiag code into a PNG output file.
    """
    draw = None
    fontmap = get_fontmap(self)
    try:
        tree = actdiag.core.parser.parse_string(code)
        diagram = actdiag.core.builder.ScreenNodeBuilder.build(tree)

        for lane in diagram.lanes:
            if lane.href:
                lane.href = resolve_reference(self, lane.href, options)
        for node in diagram.traverse_nodes():
            if node.href:
                node.href = resolve_reference(self, node.href, options)

        antialias = self.builder.config.actdiag_antialias
        draw = actdiag.core.drawer.DiagramDraw(format, diagram, filename,
                                               fontmap=fontmap, antialias=antialias)
    except Exception as e:
        if self.builder.config.actdiag_debug:
            traceback.print_exc()

        raise ActdiagError('actdiag error:\n%s\n' % e)

    return draw


def make_svgtag(self, image, relfn, trelfn, outfn,
                alt, thumb_size, image_size):
    svgtag_format = """<svg xmlns="http://www.w3.org/2000/svg"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    alt="%s" width="%s" height="%s">%s
    </svg>"""

    code = io.open(outfn, 'r', encoding='utf-8-sig').read()

    return (svgtag_format %
            (alt, image_size[0], image_size[1], code))


def make_imgtag(self, image, relfn, trelfn, outfn,
                alt, thumb_size, image_size):
    result = ""

    clickable_map = []
    for l in image.diagram.lanes:
        if l.href:
            cell = image.metrics.lane_headerbox(l)
            clickable_map.append((cell, l.href))
    for n in image.nodes:
        if n.href:
            cell = image.metrics.cell(n)
            clickable_map.append((cell, n.href))

    if clickable_map:
        imgtag_format = '<img src="%s" alt="%s" width="%s" '
        imgtag_format += 'usemap="#map_%d" height="%%s" />\n' % id(image)
    else:
        imgtag_format = '<img src="%s" alt="%s" width="%s" height="%s" />\n'

    if trelfn:
        result += ('<a href="%s">' % relfn)
        result += (imgtag_format %
                   (trelfn, alt, thumb_size[0], thumb_size[1]))
        result += ('</a>')
    else:
        result += (imgtag_format %
                   (relfn, alt, image_size[0], image_size[1]))

    if clickable_map:
        result += ('<map name="map_%d">' % id(image))
        rect_format = '<area shape="rect" coords="%s,%s,%s,%s" href="%s">'
        for m in clickable_map:
            x1 = m[0][0]
            y1 = m[0][1]
            x2 = m[0][2]
            y2 = m[0][3]
            result += (rect_format % (x1, y1, x2, y2, m[1]))

        result += ('</map>')

    return result


def render_dot_html(self, node, code, options, prefix='actdiag',
                    imgcls=None, alt=None):
    trelfn = None
    thumb_size = None
    try:
        format = self.builder.config.actdiag_html_image_format
        relfn, outfn = get_image_filename(self, code, format, options, prefix)

        options['current_docname'] = self.builder.current_docname
        image = create_actdiag(self, code, format, outfn, options, prefix)
        if not os.path.isfile(outfn):
            image.draw()
            image.save()

        # generate thumbnails
        image_size = image.pagesize()
        if 'maxwidth' in options and options['maxwidth'] < image_size[0]:
            thumb_prefix = prefix + '_thumb'
            trelfn, toutfn = get_image_filename(self, code, format,
                                                options, thumb_prefix)

            ratio = float(options['maxwidth']) / image_size[0]
            thumb_size = (options['maxwidth'], image_size[1] * ratio)
            if not os.path.isfile(toutfn):
                image.filename = toutfn
                image.save(thumb_size)

    except UnicodeEncodeError:
        msg = ("actdiag error: UnicodeEncodeError caught "
               "(check your font settings)")
        self.builder.warn(msg)
        raise nodes.SkipNode
    except ActdiagError as exc:
        self.builder.warn('dot code %r: ' % code + str(exc))
        raise nodes.SkipNode

    self.body.append(self.starttag(node, 'p', CLASS='actdiag'))
    if relfn is None:
        self.body.append(self.encode(code))
    else:
        if alt is None:
            alt = node.get('alt', self.encode(code).strip())

        if format.upper() == 'SVG':
            tagfunc = make_svgtag
        else:
            tagfunc = make_imgtag

        self.body.append(tagfunc(self, image, relfn, trelfn, outfn, alt,
                                 thumb_size, image_size))

    self.body.append('</p>\n')
    raise nodes.SkipNode


def html_visit_actdiag(self, node):
    render_dot_html(self, node, node['code'], node['options'])


def render_dot_latex(self, node, code, options, prefix='actdiag'):
    try:
        format = self.builder.config.actdiag_tex_image_format
        fname, outfn = get_image_filename(self, code, format, options, prefix)

        image = create_actdiag(self, code, format, outfn, options, prefix)
        if not os.path.isfile(outfn):
            image.draw()
            image.save()

    except ActdiagError as exc:
        self.builder.warn('dot code %r: ' % code + str(exc))
        raise nodes.SkipNode

    if fname is not None:
        self.body.append('\\par\\includegraphics{%s}\\par' % fname)
    raise nodes.SkipNode


def latex_visit_actdiag(self, node):
    render_dot_latex(self, node, node['code'], node['options'])


def on_doctree_resolved(self, doctree, docname):
    if self.builder.name in ('gettext', 'singlehtml', 'html', 'latex', 'epub'):
        return

    for node in doctree.traverse(actdiag.utils.rst.nodes.actdiag):
        code = node['code']
        prefix = 'actdiag'
        format = 'PNG'
        options = node['options']
        relfn, outfn = get_image_filename(self, code, format, options, prefix)

        image = create_actdiag(self, code, format, outfn, options, prefix)
        if not os.path.isfile(outfn):
            image.draw()
            image.save()

        candidates = {'image/png': relfn}
        image = nodes.image(uri=outfn, candidates=candidates)
        node.parent.replace(node, image)


def setup(app):
    app.add_node(actdiag.utils.rst.nodes.actdiag,
                 html=(html_visit_actdiag, None),
                 latex=(latex_visit_actdiag, None))
    app.add_directive('actdiag', Actdiag)
    app.add_config_value('actdiag_fontpath', None, 'html')
    app.add_config_value('actdiag_fontmap', None, 'html')
    app.add_config_value('actdiag_antialias', False, 'html')
    app.add_config_value('actdiag_debug', False, 'html')
    app.add_config_value('actdiag_html_image_format', 'PNG', 'html')
    app.add_config_value('actdiag_tex_image_format', 'PNG', 'html')
    app.connect("doctree-resolved", on_doctree_resolved)
