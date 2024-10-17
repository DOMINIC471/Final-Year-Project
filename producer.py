from confluent_kafka import Producer

def delivery_report(err, msg):
    """ Called once for each message produced to indicate delivery result.
        Triggered by poll() or flush(). """
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

p = Producer({'bootstrap.servers': 'localhost:9092'})

# Produce message
p.produce('test-topic', key='key', value='Hello Kafka!', callback=delivery_report)

# Wait for any outstanding messages to be delivered and delivery reports received
p.flush()
