# -*- coding: utf-8 -*-
# Standard imports
import os
from packaging import version
from fnmatch import fnmatch
from codecs import open

# Custom imports
import csscompressor
import htmlmin

# Pelican imports
from pelican import signals


if version.parse(csscompressor.__version__) <= version.parse("0.9.5"):
    # Monkey patch csscompressor 0.9.5
    _preserve_call_tokens_original = csscompressor._preserve_call_tokens
    _url_re = csscompressor._url_re

    def my_new_preserve_call_tokens(*args, **kwargs):
        """If regex is for url pattern, switch the keyword remove_ws to False

        Such configuration will preserve svg code in url() pattern of CSS file.
        """
        if _url_re == args[1]:
            kwargs["remove_ws"] = False
        return _preserve_call_tokens_original(*args, **kwargs)

    csscompressor._preserve_call_tokens = my_new_preserve_call_tokens

    assert csscompressor._preserve_call_tokens == my_new_preserve_call_tokens


class Minification(object):
    """
    Class that does file content minification.
    """
    def __init__(self, pelican):
        """
        Minifies the files.
        :param pelican: the pelican object
        :type pelican: pelican.Pelican
        """
        for path, subdirs, files in os.walk(pelican.output_path):
            for name in files:
                path_file = os.path.join(path, name)

                if fnmatch(name, '*.html'):
                    self.write_to_file(
                        path_file,
                        lambda content: htmlmin.minify(
                            content,
                            remove_comments=True,
                            remove_empty_space=True,
                            reduce_boolean_attributes=True,
                            keep_pre=True,
                            remove_optional_attribute_quotes=False,
                        )
                    )
                elif fnmatch(name, '*.css'):
                    self.write_to_file(
                        path_file,
                        lambda content: csscompressor.compress(content)
                    )

    @staticmethod
    def write_to_file(path_file, callback):
        """
        Reads the content of the given file, puts the content into the callback and writes the result back to the file.
        :param path_file: the path to the file
        :type path_file: str
        :param callback: the callback function
        :type callback: function
        """
        try:
            with open(path_file, 'r+', encoding='utf-8') as f:
                content = callback(f.read())
                f.seek(0)
                f.write(content)
                f.truncate()
        except Exception as e:
            raise Exception(
                'unable to minify file %(file)s, exception was %(exception)r' % {
                    'file': path_file,
                    'exception': e,
                }
            )


def register():
    """
    Registers after the content was generated.
    """
    signals.finalized.connect(Minification)
