from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_deployment(api, app_config, namespace):
    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(
            name=app_config["metadata"]["name"],
            namespace=namespace
        ),
        spec=client.V1DeploymentSpec(
            replicas=app_config["spec"]["replicas"],
            selector=client.V1LabelSelector(
                match_labels={"app": app_config["spec"]["appName"]}
            ),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels={"app": app_config["spec"]["appName"]}
                ),
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name=app_config["spec"]["appName"],
                            image=app_config["spec"]["image"],
                            ports=[client.V1ContainerPort(container_port=app_config["spec"]["port"])],
                            env=[client.V1EnvVar(name=env["name"], value=env["value"]) 
                                 for env in app_config["spec"].get("env", [])]
                        )
                    ]
                )
            )
        )
    )
    
    try:
        api.create_namespaced_deployment(namespace=namespace, body=deployment)
        logger.info(f"Deployment {app_config['metadata']['name']} created")
    except ApiException as e:
        if e.status == 409:  # Already exists
            api.replace_namespaced_deployment(
                name=app_config["metadata"]["name"],
                namespace=namespace,
                body=deployment
            )
            logger.info(f"Deployment {app_config['metadata']['name']} updated")
        else:
            raise

def create_service(api, app_config, namespace):
    service = client.V1Service(
        metadata=client.V1ObjectMeta(
            name=app_config["metadata"]["name"],
            namespace=namespace
        ),
        spec=client.V1ServiceSpec(
            selector={"app": app_config["spec"]["appName"]},
            ports=[client.V1ServicePort(port=app_config["spec"]["port"])]
        )
    )
    
    try:
        api.create_namespaced_service(namespace=namespace, body=service)
        logger.info(f"Service {app_config['metadata']['name']} created")
    except ApiException as e:
        if e.status == 409:  # Already exists
            api.replace_namespaced_service(
                name=app_config["metadata"]["name"],
                namespace=namespace,
                body=service
            )
            logger.info(f"Service {app_config['metadata']['name']} updated")
        else:
            raise

def main():
    config.load_kube_config()
    
    api_client = client.ApiClient()
    apps_v1 = client.AppsV1Api(api_client)
    core_v1 = client.CoreV1Api(api_client)
    custom_api = client.CustomObjectsApi(api_client)
    
    resource_version = ""
    
    while True:
        try:
            w = watch.Watch()
            for event in w.stream(custom_api.list_cluster_custom_object,
                                group="stable.example.com",
                                version="v1",
                                plural="appconfigs",
                                resource_version=resource_version):
                logger.info(f"收到事件类型: {event['type']}, 资源名称: {event['object']['metadata']['name']}")
                app_config = event["object"]
                namespace = app_config["metadata"]["namespace"]
                
                if event["type"] in ["ADDED", "MODIFIED"]:
                    create_deployment(apps_v1, app_config, namespace)
                    create_service(core_v1, app_config, namespace)
                elif event["type"] == "DELETED":
                    try:
                        apps_v1.delete_namespaced_deployment(
                            name=app_config["metadata"]["name"],
                            namespace=namespace
                        )
                        core_v1.delete_namespaced_service(
                            name=app_config["metadata"]["name"],
                            namespace=namespace
                        )
                        logger.info(f"Resources for {app_config['metadata']['name']} deleted")
                    except ApiException as e:
                        if e.status != 404:  # Ignore if already deleted
                            raise
                
                resource_version = event["object"]["metadata"]["resourceVersion"]
                
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()