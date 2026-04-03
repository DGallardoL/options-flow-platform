#!/bin/bash
# =============================================================================
# MongoDB Sharded Cluster Initialization Reference Script
# =============================================================================
#
# NOTE: This script documents the initialization steps. The actual
# initialization is performed by setup.sh using 'docker exec' commands
# to connect from INSIDE each container (required for MongoDB's localhost
# exception when keyFile auth is enabled).
#
# If you need to re-initialize manually, run these commands in order:
#
# Step 1: Init Config Server RS
#   docker exec configsvr1 mongosh --port 27100 --eval 'rs.initiate({_id:"configrs",configsvr:true,members:[{_id:0,host:"configsvr1:27100"}]})'
#
# Step 2: Init Shard 1 RS
#   docker exec mongo1 mongosh --port 27017 --eval 'rs.initiate({_id:"rs0",members:[{_id:0,host:"mongo1:27017",priority:2},{_id:1,host:"mongo2:27018"},{_id:2,host:"mongo3:27019"}]})'
#
# Step 3: Init Shard 2 RS
#   docker exec mongo4 mongosh --port 27020 --eval 'rs.initiate({_id:"rs1",members:[{_id:0,host:"mongo4:27020",priority:2},{_id:1,host:"mongo5:27021"},{_id:2,host:"mongo6:27022"}]})'
#
# Step 4: Create admin user (from inside mongos = localhost exception)
#   docker exec mongos mongosh --port 27025 --eval "db.getSiblingDB('admin').createUser({user:'admin',pwd:'PASSWORD',roles:[{role:'root',db:'admin'}]})"
#
# Step 5: Add shards
#   docker exec mongos mongosh --port 27025 -u admin -p PASSWORD --authenticationDatabase admin --eval 'sh.addShard("rs0/mongo1:27017,mongo2:27018,mongo3:27019"); sh.addShard("rs1/mongo4:27020,mongo5:27021,mongo6:27022")'
#
# Step 6: Enable sharding + shard collections
#   (see setup.sh step 6f for full commands)
#
# Step 7: Create RBAC users
#   (see setup.sh step 6g for full commands)
#
# Step 8: Create indexes
#   (see setup.sh step 6h or scripts/init_indexes.js)
#
# =============================================================================

echo "This script is a reference. Run 'bash setup.sh' for actual initialization."
echo "See setup.sh for the full initialization procedure using docker exec."
