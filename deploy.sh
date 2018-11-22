docker kill $(docker ps -aq)
docker rm $(docker ps -aq)
docker rmi $(docker images -aq)

docker run -d -p 80:80 --restart=unless-stopped --log-opt max-size=100m --log-opt mode=non-blocking chebyrash/yablach-censor