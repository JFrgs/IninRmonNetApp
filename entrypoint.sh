#!/bin/sh

cd /app && \
    # echo "python3 NetApp.py -n $NET_APP_NAME -t $NET_API_PROT -s $NET_API_HOST -p $NET_API_PORT -U $NET_API_USER -P $NET_API_PASS -c $CALLBACK_HOST -m $CALLBACK_PORT -q $COLLECTOR_HOST -o $COLLECTOR_USER -r $COLLECTOR_PASS" -z $MN_HOST -Z $MN_TOKEN &&\ 
    python3 NetApp.py \
   -n $NET_APP_NAME \
   -t $NET_API_PROT \
   -s $NET_API_HOST \
   -p $NET_API_PORT \
   -U $NET_API_USER \
   -P $NET_API_PASS \
   -c $CALLBACK_HOST \
   -m $CALLBACK_PORT \
   -q $COLLECTOR_HOST \
   -o $COLLECTOR_USER \
   -r $COLLECTOR_PASS \
   -z $MN_HOST \
   -Z $MN_TOKEN

