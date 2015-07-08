# CloudFormation template
# Author:       Raphael Rabelo
# Github:       https://github.com/rabeloo
# Description:  Create an instance with autoscalling, metadata and userdata configs.
#               You can adapt for your needs, adding or removing things.
import inspect
import troposphere.cloudformation as cf
import troposphere.ec2 as ec2
from troposphere import cloudformation as cf
from troposphere import (Base64, FindInMap, GetAtt, GetAZs, Join, Output, Parameter, Ref, Template, autoscaling)
from troposphere.autoscaling import (AutoScalingGroup, ScalingPolicy, LaunchConfiguration, Metadata, Tag)
from troposphere.iam import PolicyType, Role, InstanceProfile

## Fast Settings
# Tip: Put your main configs here:
instance_type       = "t2.micro"
security_groups_ids = ["sg-xxxxxxxx"]
ami_id              = "ami-xxxxxxxx"
elb_name            = ["elb_name_here"]
availability_zones  = ["us-east-1a","us-east-1b"] # Tip: You can try GetAZs("")
subnet_ids          = ["subnet-xxxxxxxx", "subnet-xxxxxxxx"]

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
  Description           = "Choose instance type for EC2",
  ConstraintDescription = "must be a valid EC2 instance type",
  Default               = instance_type,
  Type                  = "String",
  AllowedValues         = [
    "t2.micro"  , "t2.small"  , "t2.medium"  ,
    "m3.medium" , "m3.large"  , "m3.xlarge"  , "m3.2xlarge" ,
    "c3.large"  , "c3.xlarge" , "c3.2xlarge" , "c3.4xlarge" , "c3.8xlarge"  ,
    "c4.large"  , "c4.xlarge" , "c4.2xlarge" , "c4.4xlarge" , "c4.8xlarge"  ,
    "r3.large"  , "r3.xlarge" , "r3.2xlarge" , "r3.4xlarge" , "r3.8xlarge"] ,
))

minInstances_param = t.add_parameter(Parameter("MinNumInstances",
  Type                  = "Number",
  Description           = "Number of minimum instances",
  ConstraintDescription = "Must be less than MaxNumInstances",
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
    "us-east-1" : {
      "AMIid"   : ami_id,
      "SGid"    : security_groups_ids,
      "SNETid"  : subnet_ids,
      "ELBName" : elb_name,
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

iam_policy_resource = t.add_resource(PolicyType(
  "IAMPolicy",
  PolicyName      = "bootstrap",
  Roles           = [Ref(iam_role_resource)],
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

iam_instanceprofile_resource = t.add_resource(InstanceProfile(
    "IAMInstanceProfile",
    Path            = "/",
    Roles           = [Ref(iam_role_resource)]
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
  )),
  Metadata=Metadata(
    cf.Init({
      "configsets" : cf.InitConfigSets(InstallandRun = [ "install", "config" ] ),
      "install" : cf.InitConfig(packages = { "yum" : { "git" : [] , "wget" : [] } }),
      "config" : cf.InitConfig(
        files = cf.InitFiles({
          "/tmp/example.txt" : cf.InitFile(
            content = Join('', [
              "This is a file example.\n",
              "See another examples in:\n",
              "https://github.com/rabeloo/cf-templates\n"
            ]),
            owner = "root",
            group = "root",
            mode = "000600"
          )
        }),
      ),
    })
  )
))

autoscaling_group_resource = t.add_resource(AutoScalingGroup(
  "myAutoScalingGroup",
  DesiredCapacity          = Ref(desInstances_param),
  MinSize                  = Ref(minInstances_param),
  MaxSize                  = Ref(maxInstances_param),
  Cooldown                 = "300",
  LoadBalancerNames        = FindInMap("RegionMap", { "Ref" : "AWS::Region" }, "ELBName" ),
  AvailabilityZones        = availability_zones,
  LaunchConfigurationName  = Ref(launchconfig_resource),
  VPCZoneIdentifier        = FindInMap( "RegionMap", { "Ref" : "AWS::Region"}, "SNETid" ),
  Tags                     = [Tag( "Name", "MyInstance", True ), Tag( "Project", "MyProject", True ), Tag( "Team", "MyTeam", True )]
))

autoscaling_up_resource    = t.add_resource(ScalingPolicy(
    "myScalingUp",
    AdjustmentType         = "ChangeInCapacity",
    ScalingAdjustment      = "1",
    Cooldown               = "300",
    AutoScalingGroupName   = Ref(autoscaling_group_resource)
))

autoscaling_down_resource    = t.add_resource(ScalingPolicy(
    "myScalingDown",
    AdjustmentType         = "ChangeInCapacity",
    ScalingAdjustment      = "-1",
    Cooldown               = "300",
    AutoScalingGroupName   = Ref(autoscaling_group_resource)
))

# Printing json template
filename = inspect.getfile(inspect.currentframe(0))
t_json = t.to_json()
file=open('./' + filename + '.json','w')
file.write(t_json)
