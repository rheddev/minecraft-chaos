#!/bin/sh
cd "./server"
exec java -Xms1024M -Xmx2048M -jar server.jar --nogui
