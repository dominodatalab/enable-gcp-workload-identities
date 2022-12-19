tag="${tag:-latest}"
operator_image="${operator_image:-quay.io/domino/gcpworkloadidentity}"
docker build -f ./Dockerfile -t ${operator_image}:${tag} .
docker push ${operator_image}:${tag}