#!/bin/sh
# @Author: ahuynh
# @Date:   2015-06-10 16:55:53
# @Last Modified by:   ahuynh
# @Last Modified time: 2015-06-12 10:09:03

# Build a new image
docker build -t a5huynh/sidekick .;

# Remove old images
docker rmi $(docker images -aq -f dangling=true);