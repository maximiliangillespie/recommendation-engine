# recommendation-engine
## TO GET STARTED:

### IN COMMAND LINE: 
1. docker run -d --name redis-stack-server -p 6379:6379 redis/redis-stack-server:latest
2. (open new tab) pip3 install -r requirements.txt
3. python3 demo.py

### IN POSTMAN:

1. Load the API routes into your postman app via this link: https://www.getpostman.com/collections/17efb9d11ae104f5a419
2. Query to load data, flush, add individual scores, get suggestions based on user id