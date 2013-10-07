import re
import os
import codecs

from glue import __version__
from base import JinjaTextFormat

from ..exceptions import ValidationError


class CssFormat(JinjaTextFormat):

    camelcase_separator = 'camelcase'
    css_pseudo_classes = set(['link', 'visited', 'active', 'hover', 'focus',
                              'first-letter', 'first-line', 'first-child',
                              'before', 'after'])

    template = u"""
        /* glue: {{ version }} hash: {{ hash }} */
        {% for image in images %}.{{ image.label }}{{ image.pseudo }}{%- if not image.last %}, {%- endif %}{%- endfor %}{
            background-image:url('{{ sprite_path }}');
            background-repeat:no-repeat;
        }
        {% for image in images %}
        .{{ image.label }}{{ image.pseudo }}{
            background-position:{{ image.x ~ ('px' if image.x) }} {{ image.y ~ ('px' if image.y) }};
            width:{{ image.width }}px;
            height:{{ image.height }}px;
        }
        {% endfor %}
        {% for ratio in ratios %}
        @media screen and (-webkit-min-device-pixel-ratio: {{ ratio.ratio }}), screen and (min--moz-device-pixel-ratio: {{ ratio.ratio }}),screen and (-o-min-device-pixel-ratio: {{ ratio.fraction }}),screen and (min-device-pixel-ratio: {{ ratio.ratio }}){
            {% for image in images %}.{{ image.label }}{{ image.pseudo }}{% if not image.last %}, {% endif %}
            {% endfor %}{
                background-image:url('{{ ratio.sprite_path }}');
                -webkit-background-size: {{ width }}px {{ height }}px;
                -moz-background-size: {{ width }}px {{ height }}px;
                background-size: {{ width }}px {{ height }}px;
            }
        }
        {% endfor %}
        """

    @classmethod
    def populate_argument_parser(cls, parser):
        group = parser.add_argument_group("CSS format options")

        group.add_argument("--css",
                           dest="css_dir",
                           nargs='?',
                           const=True,
                           default=os.environ.get('GLUE_CSS', True),
                           metavar='DIR',
                           help="Generate CSS files and optionally where")

        group.add_argument("--less",
                           dest="css_format",
                           action='store_const',
                           const='less',
                           default=os.environ.get('GLUE_LESS', 'css'),
                           help="Use .less instead of .css as CSS file format")

        group.add_argument("--scss",
                           dest="css_format",
                           action='store_const',
                           const='scss',
                           default=os.environ.get('GLUE_LESS', 'css'),
                           help="Use .scss instead of .css as CSS file format")

        group.add_argument("--namespace",
                           dest="css_namespace",
                           type=unicode,
                           default=os.environ.get('GLUE_CSS_NAMESPACE', 'sprite'),
                           help="Namespace for all css classes (default: sprite)")

        group.add_argument("--sprite-namespace",
                           dest="css_sprite_namespace",
                           type=unicode,
                           default=os.environ.get('GLUE_CSS_SPRITE_NAMESPACE',
                                                  '{sprite_name}'),
                           help="Namespace for all sprites (default: {sprite_name})")

        group.add_argument("-u", "--url",
                           dest="css_url",
                           type=unicode,
                           default=os.environ.get('GLUE_CSS_URL', ''),
                           help="Pprepend this string to the sprites path")

        group.add_argument("--cachebuster",
                           dest="css_cachebuster",
                           default=os.environ.get('GLUE_CSS_CACHEBUSTER', False),
                           action='store_true',
                           help=("Use the sprite's sha1 first 6 characters as a "
                                 "queryarg everytime that file is referred "
                                 "from the css"))

        group.add_argument("--cachebuster-filename",
                           dest="css_cachebuster_filename",
                           default=os.environ.get('GLUE_CSS_CACHEBUSTER', False),
                           action='store_true',
                           help=("Append the sprite's sha first 6 characters "
                                 "to the otput filename"))

        group.add_argument("--separator",
                           dest="css_separator",
                           type=unicode,
                           default=os.environ.get('GLUE_CSS_SEPARATOR', '_'),
                           metavar='SEPARATOR',
                           help=("Customize the separator used to join CSS class "
                                 "names. If you want to use camelCase use "
                                 "'camelcase' as separator."))

        group.add_argument("--css-template",
                           dest="css_template",
                           default=os.environ.get('GLUE_CSS_TEMPLATE', None),
                           metavar='DIR',
                           help="Template to use to generate the CSS output.")

    @classmethod
    def apply_parser_contraints(cls, parser, options):
        if options.css_cachebuster and options.css_cachebuster_filename:
            parser.error("You can't use --cachebuster and "
                         "--cachebuster-filename at the same time.")

    @property
    def extension(self):
        return self.sprite.config['css_format']

    def needs_rebuild(self):
        hash_line = '/* glue: %s hash: %s */\n' % (__version__, self.sprite.hash)
        try:
            assert not self.sprite.config['force']
            with codecs.open(self.output_path(), 'r', 'utf-8-sig') as existing_css:
                first_line = existing_css.readline()
                assert first_line == hash_line
        except Exception:
            return True
        return False

    def validate(self):
        class_names = [i.label for i in self.sprite.images]

        if len(set(class_names)) != len(self.sprite.images):
            dup = [i for i in self.sprite.images if class_names.count(i.label) > 1]
            duptext = '\n'.join(['\t{0} => .{1}'.format(os.path.relpath(d.path), d.label) for d in dup])
            raise ValidationError("Error: Some images will have the same class name:\n{0}".format(duptext))
        return True

    def get_context(self):

        context = super(CssFormat, self).get_context()

        # Generate css labels
        for image in context['images']:
            image['label'], image['pseudo'] = self.generate_css_name(image['filename'])

        # Add cachebuster if required
        if self.sprite.config['css_cachebuster']:

            def apply_cachebuster(path):
                return "%s?%s" % (path, self.sprite.hash)

            context['sprite_path'] = apply_cachebuster(context['sprite_path'])

            for ratio in context['ratios']:
                ratio['sprite_path'] = apply_cachebuster(ratio['sprite_path'])

        return context

    def generate_css_name(self, filename):
        separator = self.sprite.config['css_separator']
        namespace = [re.sub(r'[^\w\-_]', '', filename.rsplit('.', 1)[0])]

        # Add sprite namespace if required
        if self.sprite.config['css_sprite_namespace']:
            sprite_name = re.sub(r'[^\w\-_]', '', self.sprite.name)
            namespace.insert(0, self.sprite.config['css_sprite_namespace'].format(sprite_name=sprite_name))

        # Add global namespace if required
        if self.sprite.config['css_namespace']:
            namespace.insert(0, self.sprite.config['css_namespace'])

        # Handle CamelCase separator
        if self.sprite.config['css_separator'] == self.camelcase_separator:
            namespace = [n[:1].title() + n[1:] if i > 0 else n for i, n in enumerate(namespace)]
            separator = ''

        label = separator.join(namespace)
        pseudo = ''

        if '__' in filename:
            pseudo = set(filename.split('__')).intersection(self.css_pseudo_classes)

            # If present add this pseudo class as pseudo an remove it from the label
            if pseudo:
                pseudo = list(pseudo)[-1]
                pseudo = ':%s' % pseudo
                label = label.replace('__%s' % pseudo, '')

        return label, pseudo