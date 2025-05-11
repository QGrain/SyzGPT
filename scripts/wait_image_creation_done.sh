#!/bin/bash
echo "Waiting for image creation to complete..."
while screen -ls | grep -q "syzqemuctl-template-creation"; do
    echo "Image creation still running...waiting for 60 seconds."
    sleep 60
done
echo "Image creation completed!"