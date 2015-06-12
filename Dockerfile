FROM python:3.4.3-onbuild
MAINTAINER Andrew Huynh <andrew@productbio.com>

ENV LAST_UPDATED 2015-06-12

ENTRYPOINT [ "python", "sidekick.py" ]
