# -*- coding: utf-8 -*-
# Standard imports
import os
from packaging import version
from functools import lru_cache
from fnmatch import fnmatch
from codecs import open
import logging

# Custom imports
import csscompressor
from jsmin import jsmin
import htmlmin
from bs4 import BeautifulSoup

# Pelican imports
from pelican import signals

__version__ = "0.2.0"

LOGGER = logging.getLogger(__name__)

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


class Minification:
    """File content minification"""

    def __init__(self, pelican):
        """Minifies the files

        :param pelican: the pelican object
        :type pelican: pelican.Pelican
        """
        LOGGER.info("Minification in progress...")

        for path, subdirs, files in os.walk(pelican.output_path):
            for name in files:
                path_file = os.path.join(path, name)

                if fnmatch(name, "*.html"):
                    self.write_to_file(
                        path_file,
                        lambda content: self.minify_inline_script_style(
                            htmlmin.minify(
                                content,
                                remove_comments=True,
                                remove_empty_space=True,
                                reduce_boolean_attributes=True,
                                keep_pre=True,
                                remove_optional_attribute_quotes=False,
                            )
                        ),
                    )
                elif fnmatch(name, "*.css"):
                    self.write_to_file(
                        path_file, lambda content: csscompressor.compress(content)
                    )

    def minify_inline_script_style(self, content):
        """Minify inline JavaScript and CSS in HTML content

        :param content: HTML data
        :type content: <str>
        :return: HTML data with <script> and <style> tags minified
        :rtype: <str>
        """
        soup = BeautifulSoup(content, "html.parser")

        # Compression methods according to specific HTML tags
        tags_methods = {"script": jsmin, "style": csscompressor.compress}

        content_modified = False
        for tag, method in tags_methods.items():

            found_tags = soup.find_all(tag)
            if not found_tags:
                continue

            for found_tag in found_tags:
                # Exclude empty tags
                if not found_tag.string:
                    continue
                content_modified = True
                found_tag.string.replace_with(
                    minification_method(method, found_tag.string)
                )

        # Return content as is if there have been no changes
        return str(soup) if content_modified else content

    @staticmethod
    def write_to_file(path_file, callback):
        """Read the content of the given file, put the content into the callback
        and writes the result back to the file.

        :param path_file: the path to the file
        :type path_file: str
        :param callback: the callback function
        :type callback: function
        """
        try:
            with open(path_file, "r+", encoding="utf-8") as f:
                content = callback(f.read())
                f.seek(0)
                f.write(content)
                f.truncate()
        except Exception as e:
            raise Exception(
                "unable to minify file %(file)s, exception was %(exception)r"
                % {"file": path_file, "exception": e}
            )


@lru_cache(maxsize=None)
def minification_method(method, content):
    """Cached wrapper for minification method

    Some JavaScript or CSS tags may be similar from page to page;
    so caching the return of this function can speed up the minification process.

    :param content: JavaScript or CSS code
    :type content: <str>
    :return: Minified code
    :rtype: <str>
    """
    return method(content)


def register():
    """Register the plugin after the content was generated"""
    signals.finalized.connect(Minification)
