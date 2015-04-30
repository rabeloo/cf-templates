# CloudFormation template
# Author:       Raphael Rabelo
# Github:       https://github.com/rabeloo
# Description:  Create an instance with autoscalling, metadata and userdata configs.
#               You can adapt for you needs, adding or removing things.

from troposphere import Base64, FindInMap, GetAtt, GetAZs, Join
from troposphere import Parameter, Output, Ref, Template
from troposphere import cloudformation, autoscaling
from troposphere.iam import Role, PolicyType
from troposphere.autoscaling import AutoScalingGroup, Tag
from troposphere.autoscaling import LaunchConfiguration
import troposphere.ec2 as ec2

## Fast Settings
# Tip: Put your
instance_type       = "m3.medium"
security_groups_ids = "sg-xxxxxx"
ami_id              = "ami-xxxxxx"
subnet_ids          = ["subnet-xxxxxx", "subnet-xxxxxx", "subnet-xxxxxx"]

# Template {}
t = Template()

t.add_description("An EC2 instances with AutoScalling Group")
t.add_version("2010-09-09")

## Parameters {}
keyname_param = t.add_parameter(Parameter("KeyName",
  Description = "Name of an existing EC2 keypair",
  Type        = "String"
))

instanceType_param = t.add_parameter(Parameter("InstanceType",
  Description           = "My instances",
  ConstraintDescription = "must be a valid EC2 instance type",
  Default               = instance_type,
  Type                  = "String"
))

minInstances_param = t.add_parameter(Parameter("MinNumInstances",
  Type                  = "Number",
  Description           = "Number of minimum instances",
  ConstraintDescription = "Must be less than MaxNumInstances",
  AllowedValues         = [
    "t2.micro", "t2.small", "t2.medium",
    "m3.medium", "m3.large", "m3.xlarge", "m3.2xlarge",
    "c3.large", "c3.xlarge", "c3.2xlarge", "c3.4xlarge", "c3.8xlarge",
    "c4.large", "c4.xlarge", "c4.2xlarge", "c4.4xlarge", "c4.8xlarge",
    "r3.large", "r3.xlarge", "r3.2xlarge", "r3.4xlarge", "r3.8xlarge"],
  Default               = "1",
))

maxInstances_param = t.add_parameter(Parameter("MaxNumInstances",
  Description           = "Number of maximum instances",
  ConstraintDescription = "Must be greater than MinNumInstances",
  Default               = "1",
  Type                  = "Number"
))

desInstances_param = t.add_parameter(Parameter("DesNumInstances",
  Description           = "Number of instances that need to be running before creation is marked as complete.",
  ConstraintDescription = "Must be in the range specified by MinNumInstances and MaxNumInstances.",
  Default               = "1",
  Type                  = "Number"
))

## Mappings
region_map = t.add_mapping('RegionMap', {
    "sa-east-1" : {
      "AMIid"   : ami_id,
      "SGid"    : security_groups_ids,
      "SNETid"  : subnet_ids
    }}
)

## Resources

iam_role_resource = t.add_resource(Role(
  "IAMRole",
  Path  = "/",
  AssumeRolePolicyDocument  =
   {
     "Version":"2012-10-17",
     "Statement":[
      {
        "Action":[
          "sts:AssumeRole"
        ],
        "Effect":"Allow",
        "Principal":{
          "Service":[
            "ec2.amazonaws.com"
          ]
        }
      }
     ]
   }
))

iam_instanceprofile_resource = t.add_resource(PolicyType(
  "IAMPolicy",
  PolicyName      = "bootstrap",
  Roles           = Ref(iam_role_resource),
  PolicyDocument  =
  {
    "Version":"2012-10-17",
    "Statement":[
      {
        "Action":[ "ec2:DescribeTags", "ec2:CreateTags" ],
        "Resource":[ "*" ],
        "Effect":"Allow"
      },
      {
        "Action":[ "route53:ListHostedZones", "route53:ChangeResourceRecordSets" ],
        "Resource":[ "*" ],
        "Effect":"Allow"
      }
    ]
 }
))

launchconfig_resource = t.add_resource(LaunchConfiguration(
  "myLaunchConfig",
  ImageId             = FindInMap("RegionMap", { "Ref" : "AWS::Region" }, "AMIid"),
  SecurityGroups      = FindInMap("RegionMap", { "Ref" : "AWS::Region" }, "SGid" ),
  KeyName             = Ref(keyname_param),
  InstanceType        = Ref(instanceType_param),
  IamInstanceProfile  = Ref(iam_instanceprofile_resource),
  UserData            = Base64(Join("", [
   "#!/bin/bash\n",
   "yum clean all\n",
   "yum update -y\n",
   "yum install pystache python-daemon -y\n",
   "/bin/rpm -U https://s3.amazonaws.com/cloudformation-examples/aws-cfn-bootstrap-latest.amzn1.noarch.rpm\n",
   "/opt/aws/bin/cfn-init ",
   "         --stack ",
   {
       "Ref": "AWS::StackName"
   },
   "         --resource myLaunchConfig",
   "         --configsets InstallandRun",
   "         --region ",
   {
       "Ref": "AWS::Region"
   },
   "\n"]
  ))
))

print(t.to_json())
